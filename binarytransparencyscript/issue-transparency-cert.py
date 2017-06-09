import os
import sys
import re
import json
import inspect
import logging
import codecs
import pprint
import traceback
import shutil
from datetime import datetime
from contextlib import contextmanager
from optparse import OptionParser, Option, OptionGroup

sys.path.insert(1, os.path.dirname(os.path.dirname(sys.path[0])))


class LockedTuple(tuple):
    def __new__(cls, items):
        return tuple.__new__(cls, (make_immutable(x) for x in items))
    def __deepcopy__(self, memo):
        return [deepcopy(elem, memo) for elem in self]


def make_immutable(item):
    if isinstance(item, list) or isinstance(item, tuple):
        result = LockedTuple(item)
    elif isinstance(item, dict):
        result = ReadOnlyDict(item)
        result.lock()
    else:
        result = item
    return result


# Define our own FATAL_LEVEL
FATAL_LEVEL = logging.CRITICAL + 10
logging.addLevelName(FATAL_LEVEL, 'FATAL')

# mozharness log levels.
DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL, IGNORE = (
    'debug', 'info', 'warning', 'error', 'critical', 'fatal', 'ignore')

LOG_LEVELS = {
    DEBUG: logging.DEBUG,
    INFO: logging.INFO,
    WARNING: logging.WARNING,
    ERROR: logging.ERROR,
    CRITICAL: logging.CRITICAL,
    FATAL: FATAL_LEVEL
}

# mozharness root logger
ROOT_LOGGER = logging.getLogger()


# BaseLogger {{{1
class BaseLogger(object):
    """ Base class in charge of logging handling logic such as creating logging
    files, dirs, attaching to the console output and managing its output.

    Attributes:
        LEVELS (dict): flat copy of the `LOG_LEVELS` attribute of the `log` module.

    TODO: status? There may be a status object or status capability in
    either logging or config that allows you to count the number of
    error,critical,fatal messages for us to count up at the end (aiming
    for 0).
    """
    LEVELS = LOG_LEVELS

    def __init__(
        self, log_level=INFO,
        log_format='%(message)s',
        log_date_format='%H:%M:%S',
        log_name='test',
        log_to_console=True,
        log_dir='.',
        log_to_raw=False,
        logger_name='',
        append_to_log=False,
    ):
        """ BaseLogger constructor

        Args:
            log_level (str, optional): mozharness log level name. Defaults to INFO.
            log_format (str, optional): message format string to instantiate a
                                        `logging.Formatter`. Defaults to '%(message)s'
            log_date_format (str, optional): date format string to instantiate a
                                            `logging.Formatter`. Defaults to '%H:%M:%S'
            log_name (str, optional): name to use for the log files to be created.
                                      Defaults to 'test'
            log_to_console (bool, optional): set to True in order to create a Handler
                                             instance base on the `Logger`
                                             current instance. Defaults to True.
            log_dir (str, optional): directory location to store the log files.
                                     Defaults to '.', i.e. current working directory.
            log_to_raw (bool, optional): set to True in order to create a *raw.log
                                         file. Defaults to False.
            logger_name (str, optional): currently useless parameter. According
                                         to the code comments, it could be useful
                                         if we were to have multiple logging
                                         objects that don't trample each other.
            append_to_log (bool, optional): set to True if the logging content should
                                            be appended to old logging files. Defaults to False
        """

        self.log_format = log_format
        self.log_date_format = log_date_format
        self.log_to_console = log_to_console
        self.log_to_raw = log_to_raw
        self.log_level = log_level
        self.log_name = log_name
        self.log_dir = log_dir
        self.append_to_log = append_to_log

        # Not sure what I'm going to use this for; useless unless we
        # can have multiple logging objects that don't trample each other
        self.logger_name = logger_name

        self.all_handlers = []
        self.log_files = {}

        self.create_log_dir()

    def create_log_dir(self):
        """ create a logging directory if it doesn't exits. If there is a file with
        same name as the future logging directory it will be deleted.
        """

        if os.path.exists(self.log_dir):
            if not os.path.isdir(self.log_dir):
                os.remove(self.log_dir)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        self.abs_log_dir = os.path.abspath(self.log_dir)

    def init_message(self, name=None):
        """ log an init message stating the name passed to it, the current date
        and time and, the current working directory.

        Args:
            name (str, optional): name to use for the init log message. Defaults to
                                  the current instance class name.
        """

        if not name:
            name = self.__class__.__name__
        self.log_message("%s online at %s in %s" %
                         (name, datetime.now().strftime("%Y%m%d %H:%M:%S"),
                          os.getcwd()))

    def get_logger_level(self, level=None):
        """ translate the level name passed to it and return its numeric value
            according to `LEVELS` values.

        Args:
            level (str, optional): level name to be translated. Defaults to the current
                                   instance `log_level`.

        Returns:
            int: numeric value of the log level name passed to it or 0 (NOTSET) if the
                 name doesn't exists
        """

        if not level:
            level = self.log_level
        return self.LEVELS.get(level, logging.NOTSET)

    def get_log_formatter(self, log_format=None, date_format=None):
        """ create a `logging.Formatter` base on the log and date format.

        Args:
            log_format (str, optional): log format to use for the Formatter constructor.
                                        Defaults to the current instance log format.
            date_format (str, optional): date format to use for the Formatter constructor.
                                         Defaults to the current instance date format.

        Returns:
            logging.Formatter: instance created base on the passed arguments
        """

        if not log_format:
            log_format = self.log_format
        if not date_format:
            date_format = self.log_date_format
        return logging.Formatter(log_format, date_format)

    def new_logger(self):
        """ Create a new logger based on the ROOT_LOGGER instance. By default there are no handlers.
            The new logger becomes a member variable of the current instance as `self.logger`.
        """

        self.logger = ROOT_LOGGER
        self.logger.setLevel(self.get_logger_level())
        self._clear_handlers()
        if self.log_to_console:
            self.add_console_handler()
        if self.log_to_raw:
            self.log_files['raw'] = '%s_raw.log' % self.log_name
            self.add_file_handler(os.path.join(self.abs_log_dir,
                                               self.log_files['raw']),
                                  log_format='%(message)s')

    def _clear_handlers(self):
        """ remove all handlers stored in `self.all_handlers`.

        To prevent dups -- logging will preserve Handlers across
        objects :(
        """
        attrs = dir(self)
        if 'all_handlers' in attrs and 'logger' in attrs:
            for handler in self.all_handlers:
                self.logger.removeHandler(handler)
            self.all_handlers = []

    def __del__(self):
        """ BaseLogger class destructor; shutdown, flush and remove all handlers"""
        logging.shutdown()
        self._clear_handlers()

    def add_console_handler(self, log_level=None, log_format=None,
                            date_format=None):
        """ create a `logging.StreamHandler` using `sys.stderr` for logging the console
        output and add it to the `all_handlers` member variable

        Args:
            log_level (str, optional): useless argument. Not used here.
                                       Defaults to None.
            log_format (str, optional): format used for the Formatter attached to the
                                        StreamHandler. Defaults to None.
            date_format (str, optional): format used for the Formatter attached to the
                                         StreamHandler. Defaults to None.
        """

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.get_log_formatter(log_format=log_format,
                                                            date_format=date_format))
        self.logger.addHandler(console_handler)
        self.all_handlers.append(console_handler)

    def add_file_handler(self, log_path, log_level=None, log_format=None,
                         date_format=None):
        """ create a `logging.FileHandler` base on the path, log and date format
        and add it to the `all_handlers` member variable.

        Args:
            log_path (str): filepath to use for the `FileHandler`.
            log_level (str, optional): useless argument. Not used here.
                                       Defaults to None.
            log_format (str, optional): log format to use for the Formatter constructor.
                                        Defaults to the current instance log format.
            date_format (str, optional): date format to use for the Formatter constructor.
                                         Defaults to the current instance date format.
        """

        if not self.append_to_log and os.path.exists(log_path):
            os.remove(log_path)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(self.get_logger_level(log_level))
        file_handler.setFormatter(self.get_log_formatter(log_format=log_format,
                                                         date_format=date_format))
        self.logger.addHandler(file_handler)
        self.all_handlers.append(file_handler)

    def log_message(self, message, level=INFO, exit_code=-1, post_fatal_callback=None):
        """ Generic log method.
        There should be more options here -- do or don't split by line,
        use os.linesep instead of assuming \n, be able to pass in log level
        by name or number.

        Adding the IGNORE special level for runCommand.

        Args:
            message (str): message to log using the current `logger`
            level (str, optional): log level of the message. Defaults to INFO.
            exit_code (int, optional): exit code to use in case of a FATAL level is used.
                                       Defaults to -1.
            post_fatal_callback (function, optional): function to callback in case of
                                                      of a fatal log level. Defaults None.
        """

        if level == IGNORE:
            return
        for line in message.splitlines():
            self.logger.log(self.get_logger_level(level), line)
        if level == FATAL:
            if callable(post_fatal_callback):
                self.logger.log(FATAL_LEVEL, "Running post_fatal callback...")
                post_fatal_callback(message=message, exit_code=exit_code)
            self.logger.log(FATAL_LEVEL, 'Exiting %d' % exit_code)
            raise SystemExit(exit_code)


# MultiFileLogger {{{1
class MultiFileLogger(BaseLogger):
    """Subclass of the BaseLogger class. Create a log per log level in log_dir.
    Possibly also output to the terminal and a raw log (no prepending of level or date)
    """

    def __init__(self, logger_name='Multi',
                 log_format='%(asctime)s %(levelname)8s - %(message)s',
                 log_dir='logs', log_to_raw=True, **kwargs):
        """ MultiFileLogger constructor. Calls its superclass constructor,
        creates a new logger instance and log an init message.

        Args:
            log_format (str, optional): message format string to instantiate a
                                       `logging.Formatter`. Defaults to
                                       '%(asctime)s %(levelname)8s - %(message)s'
            log_name (str, optional): name to use for the log files to be created.
                                      Defaults to 'Multi'
            log_dir (str, optional): directory location to store the log files.
                                     Defaults to 'logs'
            log_to_raw (bool, optional): set to True in order to create a *raw.log
                                         file. Defaults to False.
            **kwargs: Arbitrary keyword arguments passed to the BaseLogger constructor
        """

        BaseLogger.__init__(self, logger_name=logger_name,
                            log_format=log_format,
                            log_to_raw=log_to_raw, log_dir=log_dir,
                            **kwargs)

        self.new_logger()
        self.init_message()

    def new_logger(self):
        """ calls the BaseLogger.new_logger method and adds a file handler per
        logging level in the `LEVELS` class attribute.
        """

        BaseLogger.new_logger(self)
        min_logger_level = self.get_logger_level(self.log_level)
        for level in self.LEVELS.keys():
            if self.get_logger_level(level) >= min_logger_level:
                self.log_files[level] = '%s_%s.log' % (self.log_name,
                                                       level)
                self.add_file_handler(os.path.join(self.abs_log_dir,
                                                   self.log_files[level]),
                                      log_level=level)


# ReadOnlyDict {{{1
class ReadOnlyDict(dict):
    def __init__(self, dictionary):
        self._lock = False
        self.update(dictionary.copy())

    def _check_lock(self):
        assert not self._lock, "ReadOnlyDict is locked!"

    def lock(self):
        for (k, v) in self.items():
            self[k] = make_immutable(v)
        self._lock = True

    def __setitem__(self, *args):
        self._check_lock()
        return dict.__setitem__(self, *args)

    def __delitem__(self, *args):
        self._check_lock()
        return dict.__delitem__(self, *args)

    def clear(self, *args):
        self._check_lock()
        return dict.clear(self, *args)

    def pop(self, *args):
        self._check_lock()
        return dict.pop(self, *args)

    def popitem(self, *args):
        self._check_lock()
        return dict.popitem(self, *args)

    def setdefault(self, *args):
        self._check_lock()
        return dict.setdefault(self, *args)

    def update(self, *args):
        self._check_lock()
        dict.update(self, *args)

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        result._lock = False
        for k, v in self.items():
            result[k] = deepcopy(v, memo)
        return result


class ExtendOption(Option):
    """from http://docs.python.org/library/optparse.html?highlight=optparse#adding-new-actions"""
    ACTIONS = Option.ACTIONS + ("extend",)
    STORE_ACTIONS = Option.STORE_ACTIONS + ("extend",)
    TYPED_ACTIONS = Option.TYPED_ACTIONS + ("extend",)
    ALWAYS_TYPED_ACTIONS = Option.ALWAYS_TYPED_ACTIONS + ("extend",)

    def take_action(self, action, dest, opt, value, values, parser):
        if action == "extend":
            lvalue = value.split(",")
            values.ensure_value(dest, []).extend(lvalue)
        else:
            Option.take_action(
                self, action, dest, opt, value, values, parser)


# optparse {{{1
class ExtendedOptionParser(OptionParser):
    """OptionParser, but with ExtendOption as the option_class.
    """
    def __init__(self, **kwargs):
        kwargs['option_class'] = ExtendOption
        OptionParser.__init__(self, **kwargs)


def PostScriptRun(func):
    """Decorator for methods that will be called after script execution.

    This is similar to PreScriptRun except it is called at the end of
    execution. The method will always be fired, even if execution fails.
    """
    func._post_run_listener = True
    return func


# BaseConfig {{{1
class BaseConfig(object):
    """Basic config setting/getting.
    """
    def __init__(self, config=None, initial_config_file=None, config_options=None,
                 all_actions=None, default_actions=None,
                 volatile_config=None, option_args=None,
                 require_config_file=False,
                 append_env_variables_from_configs=False,
                 usage="usage: %prog [options]"):
        self._config = {}
        self.all_cfg_files_and_dicts = []
        self.actions = []
        self.config_lock = False
        self.require_config_file = require_config_file
        # It allows to append env variables from multiple config files
        self.append_env_variables_from_configs = append_env_variables_from_configs

        if all_actions:
            self.all_actions = all_actions[:]
        else:
            self.all_actions = ['clobber', 'build']
        if default_actions:
            self.default_actions = default_actions[:]
        else:
            self.default_actions = self.all_actions[:]
        if volatile_config is None:
            self.volatile_config = {
                'actions': None,
                'add_actions': None,
                'no_actions': None,
            }
        else:
            self.volatile_config = deepcopy(volatile_config)

        if config:
            self.set_config(config)
        if initial_config_file:
            initial_config = parse_config_file(initial_config_file)
            self.all_cfg_files_and_dicts.append(
                (initial_config_file, initial_config)
            )
            self.set_config(initial_config)
            # Since initial_config_file is only set when running unit tests,
            # if no option_args have been specified, then the parser will
            # parse sys.argv which in this case would be the command line
            # options specified to run the tests, e.g. nosetests -v. Clearly,
            # the options passed to nosetests (such as -v) should not be
            # interpreted by mozharness as mozharness options, so we specify
            # a dummy command line with no options, so that the parser does
            # not add anything from the test invocation command line
            # arguments to the mozharness options.
            if option_args is None:
                option_args=['dummy_mozharness_script_with_no_command_line_options.py']
        if config_options is None:
            config_options = []
        self._create_config_parser(config_options, usage)
        # we allow manually passing of option args for things like nosetests
        self.parse_args(args=option_args)

    def get_read_only_config(self):
        return ReadOnlyDict(self._config)

    def _create_config_parser(self, config_options, usage):
        self.config_parser = ExtendedOptionParser(usage=usage)

        # Read values from config.json
        here = os.path.dirname(os.path.abspath(__file__))
        config_json = os.path.join(here, '../config.json')

        with open(config_json) as config_file:
             config_vars = json.load(config_file)

        self.config_parser.add_option(
            "--stage-product", action="store", dest="stage_product",
            type="string", default=config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--stage-product"],
            help="Name of product used in file server's directory structure, eg: firefox, mobile"
        )
        self.config_parser.add_option(
            "--version", action="store", dest="version",
            type="string", default=config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--version"],
            help="Version of release, eg: 39.0b5"
        )
        self.config_parser.add_option(
            "--contact", action="store", dest="contact",
            type="string", default=config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--contact"],
            help="Contact email to provide to Let's Encrypt"
        )
        self.config_parser.add_option(
            "--summary", action="store", dest="summary",
            type="string", default=config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--summary"],
            help="URL from which the SUMMARY file should be downloaded"
        )
        self.config_parser.add_option(
            "--chain", action="store", dest="chain",
            type="string", default=config_vars["ISSUE_TRANSPARENCY_CERT_ARGUMENTS"]["--chain"],
            help="File where the issued certificate chain should be written"
        )
        self.config_parser.add_option(
            "--work-dir", action="store", dest="work_dir",
            type="string", default="build",
            help="Specify the work_dir (subdir of base_work_dir)"
        )
        self.config_parser.add_option(
            "--base-work-dir", action="store", dest="base_work_dir",
            type="string", default=os.getcwd(),
            help="Specify the absolute path of the parent of the working directory"
        )
        self.config_parser.add_option(
            "-c", "--config-file", "--cfg", action="extend", dest="config_files",
            type="string", help="Specify a config file; can be repeated"
        )
        self.config_parser.add_option(
            "-C", "--opt-config-file", "--opt-cfg", action="extend",
            dest="opt_config_files", type="string", default=[],
            help="Specify an optional config file, like --config-file but with no "
                 "error if the file is missing; can be repeated"
        )
        self.config_parser.add_option(
            "--dump-config", action="store_true",
            dest="dump_config",
            help="List and dump the config generated from this run to "
                 "a JSON file."
        )
        self.config_parser.add_option(
            "--dump-config-hierarchy", action="store_true",
            dest="dump_config_hierarchy",
            help="Like --dump-config but will list and dump which config "
                 "files were used making up the config and specify their own "
                 "keys/values that were not overwritten by another cfg -- "
                 "held the highest hierarchy."
        )

        # Logging
        log_option_group = OptionGroup(self.config_parser, "Logging")
        log_option_group.add_option(
            "--log-level", action="store",
            type="choice", dest="log_level", default=INFO,
            choices=[DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL],
            help="Set log level (debug|info|warning|error|critical|fatal)"
        )
        log_option_group.add_option(
            "-q", "--quiet", action="store_false", dest="log_to_console",
            default=True, help="Don't log to the console"
        )
        log_option_group.add_option(
            "--append-to-log", action="store_true",
            dest="append_to_log", default=False,
            help="Append to the log"
        )
        log_option_group.add_option(
            "--multi-log", action="store_const", const="multi",
            dest="log_type", help="Log using MultiFileLogger"
        )
        log_option_group.add_option(
            "--simple-log", action="store_const", const="simple",
            dest="log_type", help="Log using SimpleFileLogger"
        )
        self.config_parser.add_option_group(log_option_group)

        # Actions
        action_option_group = OptionGroup(
            self.config_parser, "Actions",
            "Use these options to list or enable/disable actions."
        )
        action_option_group.add_option(
            "--list-actions", action="store_true",
            dest="list_actions",
            help="List all available actions, then exit"
        )
        action_option_group.add_option(
            "--add-action", action="extend",
            dest="add_actions", metavar="ACTIONS",
            help="Add action %s to the list of actions" % self.all_actions
        )
        action_option_group.add_option(
            "--no-action", action="extend",
            dest="no_actions", metavar="ACTIONS",
            help="Don't perform action"
        )
        for action in self.all_actions:
            action_option_group.add_option(
                "--%s" % action, action="append_const",
                dest="actions", const=action,
                help="Add %s to the limited list of actions" % action
            )
            action_option_group.add_option(
                "--no-%s" % action, action="append_const",
                dest="no_actions", const=action,
                help="Remove %s from the list of actions to perform" % action
            )
        self.config_parser.add_option_group(action_option_group)
        # Child-specified options
        # TODO error checking for overlapping options
        if config_options:
            for option in config_options:
                self.config_parser.add_option(*option[0], **option[1])

        # Initial-config-specified options
        config_options = self._config.get('config_options', None)
        if config_options:
            for option in config_options:
                self.config_parser.add_option(*option[0], **option[1])

    def set_config(self, config, overwrite=False):
        """This is probably doable some other way."""
        if self._config and not overwrite:
            self._config.update(config)
        else:
            self._config = config
        return self._config

    def get_actions(self):
        return self.actions

    def verify_actions(self, action_list, quiet=False):
        for action in action_list:
            if action not in self.all_actions:
                if not quiet:
                    print("Invalid action %s not in %s!" % (action,
                                                            self.all_actions))
                raise SystemExit(-1)
        return action_list

    def verify_actions_order(self, action_list):
        try:
            indexes = [ self.all_actions.index(elt) for elt in action_list ]
            sorted_indexes = sorted(indexes)
            for i in range(len(indexes)):
                if indexes[i] != sorted_indexes[i]:
                    print(("Action %s comes in different order in %s\n" +
                           "than in %s") % (action_list[i], action_list, self.all_actions))
                    raise SystemExit(-1)
        except ValueError as e:
            print("Invalid action found: " + str(e))
            raise SystemExit(-1)

    def list_actions(self):
        print "Actions available:"
        for a in self.all_actions:
            print "    " + ("*" if a in self.default_actions else " "), a
        raise SystemExit(0)

    def get_cfgs_from_files(self, all_config_files, options):
        """Returns the configuration derived from the list of configuration
        files.  The result is represented as a list of `(filename,
        config_dict)` tuples; they will be combined with keys in later
        dictionaries taking precedence over earlier.

        `all_config_files` is all files specified with `--config-file` and
        `--opt-config-file`; `options` is the argparse options object giving
        access to any other command-line options.

        This function is also responsible for downloading any configuration
        files specified by URL.  It uses ``parse_config_file`` in this module
        to parse individual files.

        This method can be overridden in a subclass to add extra logic to the
        way that self.config is made up.  See
        `mozharness.mozilla.building.buildbase.BuildingConfig` for an example.
        """
        all_cfg_files_and_dicts = []
        for cf in all_config_files:
            try:
                if '://' in cf:  # config file is an url
                    file_name = os.path.basename(cf)
                    file_path = os.path.join(os.getcwd(), file_name)
                    download_config_file(cf, file_path)
                    all_cfg_files_and_dicts.append(
                        (file_path, parse_config_file(file_path))
                    )
                else:
                    all_cfg_files_and_dicts.append((cf, parse_config_file(cf)))
            except Exception:
                if cf in options.opt_config_files:
                    print(
                        "WARNING: optional config file not found %s" % cf
                    )
                else:
                    raise
        return all_cfg_files_and_dicts

    def parse_args(self, args=None):
        """Parse command line arguments in a generic way.
        Return the parser object after adding the basic options, so
        child objects can manipulate it.
        """
        self.command_line = ' '.join(sys.argv)
        if args is None:
            args = sys.argv[1:]
        (options, args) = self.config_parser.parse_args(args)

        defaults = self.config_parser.defaults.copy()

        if not options.config_files:
            if self.require_config_file:
                if options.list_actions:
                    self.list_actions()
                print("Required config file not set! (use --config-file option)")
                raise SystemExit(-1)
        else:
            # this is what get_cfgs_from_files returns. It will represent each
            # config file name and its assoctiated dict
            # eg ('builds/branch_specifics.py', {'foo': 'bar'})
            # let's store this to self for things like --interpret-config-files
            self.all_cfg_files_and_dicts.extend(self.get_cfgs_from_files(
                # append opt_config to allow them to overwrite previous configs
                options.config_files + options.opt_config_files, options=options
            ))
            config = {}
            if self.append_env_variables_from_configs:
                # We only append values from various configs for the 'env' entry
                # For everything else we follow the standard behaviour
                for i, (c_file, c_dict) in enumerate(self.all_cfg_files_and_dicts):
                    for v in c_dict.keys():
                        if v == 'env' and v in config:
                            config[v].update(c_dict[v])
                        else:
                            config[v] = c_dict[v]
            else:
                for i, (c_file, c_dict) in enumerate(self.all_cfg_files_and_dicts):
                    config.update(c_dict)
            # assign or update self._config depending on if it exists or not
            #    NOTE self._config will be passed to ReadOnlyConfig's init -- a
            #    dict subclass with immutable locking capabilities -- and serve
            #    as the keys/values that make up that instance. Ultimately,
            #    this becomes self.config during BaseScript's init
            self.set_config(config)
        for key in defaults.keys():
            value = getattr(options, key)
            if value is None:
                continue
            # Don't override config_file defaults with config_parser defaults
            if key in defaults and value == defaults[key] and key in self._config:
                continue
            self._config[key] = value

        # The idea behind the volatile_config is we don't want to save this
        # info over multiple runs.  This defaults to the action-specific
        # config options, but can be anything.
        for key in self.volatile_config.keys():
            if self._config.get(key) is not None:
                self.volatile_config[key] = self._config[key]
                del(self._config[key])

        self.update_actions()
        if options.list_actions:
            self.list_actions()

        # Keep? This is for saving the volatile config in the dump_config
        self._config['volatile_config'] = self.volatile_config

        self.options = options
        self.args = args
        return (self.options, self.args)

    def update_actions(self):
        """ Update actions after reading in config.

        Seems a little complex, but the logic goes:

        First, if default_actions is specified in the config, set our
        default actions even if the script specifies other default actions.

        Without any other action-specific options, run with default actions.

        If we specify --ACTION or --only-ACTION once or multiple times,
        we want to override the default_actions list with the one(s) we list.

        Otherwise, if we specify --add-action ACTION, we want to add an
        action to the list.

        Finally, if we specify --no-ACTION, remove that from the list of
        actions to perform.
        """
        if self._config.get('default_actions'):
            default_actions = self.verify_actions(self._config['default_actions'])
            self.default_actions = default_actions
        self.verify_actions_order(self.default_actions)
        self.actions = self.default_actions[:]
        if self.volatile_config['actions']:
            actions = self.verify_actions(self.volatile_config['actions'])
            self.actions = actions
        elif self.volatile_config['add_actions']:
            actions = self.verify_actions(self.volatile_config['add_actions'])
            self.actions.extend(actions)
        if self.volatile_config['no_actions']:
            actions = self.verify_actions(self.volatile_config['no_actions'])
            for action in actions:
                if action in self.actions:
                    self.actions.remove(action)


class PlatformMixin(object):
    def _is_windows(self):
        """ check if the current operating system is Windows.

        Returns:
            bool: True if the current platform is Windows, False otherwise
        """
        system = platform.system()
        if system in ("Windows", "Microsoft"):
            return True
        if system.startswith("CYGWIN"):
            return True
        if os.name == 'nt':
            return True

    def _is_darwin(self):
        """ check if the current operating system is Darwin.

        Returns:
            bool: True if the current platform is Darwin, False otherwise
        """
        if platform.system() in ("Darwin"):
            return True
        if sys.platform.startswith("darwin"):
            return True

    def _is_linux(self):
        """ check if the current operating system is a Linux distribution.

        Returns:
            bool: True if the current platform is a Linux distro, False otherwise
        """
        if platform.system() in ("Linux"):
            return True
        if sys.platform.startswith("linux"):
            return True

    def _is_64_bit(self):
        if self._is_darwin():
            # osx is a special snowflake and to ensure the arch, it is better to use the following
            return sys.maxsize > 2**32  # context: https://docs.python.org/2/library/platform.html
        else:
            # Using machine() gives you the architecture of the host rather
            # than the build type of the Python binary
            return '64' in platform.machine()


# ScriptMixin {{{1
class ScriptMixin(PlatformMixin):
    """This mixin contains simple filesystem commands and the like.

    It also contains some very special but very complex methods that,
    together with logging and config, provide the base for all scripts
    in this harness.

    WARNING !!!
    This class depends entirely on `LogMixin` methods in such a way that it will
    only works if a class inherits from both `ScriptMixin` and `LogMixin`
    simultaneously.

    Depends on self.config of some sort.

    Attributes:
        env (dict): a mapping object representing the string environment.
        script_obj (ScriptMixin): reference to a ScriptMixin instance.
    """

    env = None
    script_obj = None

    def platform_name(self):
        """ Return the platform name on which the script is running on.
        Returns:
            None: for failure to determine the platform.
            str: The name of the platform (e.g. linux64)
        """
        return platform_name()

    # Simple filesystem commands {{{2
    def mkdir_p(self, path, error_level=ERROR):
        """ Create a directory if it doesn't exists.
        This method also logs the creation, error or current existence of the
        directory to be created.

        Args:
            path (str): path of the directory to be created.
            error_level (str): log level name to be used in case of error.

        Returns:
            None: for sucess.
            int: -1 on error
        """

        if not os.path.exists(path):
            self.info("mkdir: %s" % path)
            try:
                os.makedirs(path)
            except OSError:
                self.log("Can't create directory %s!" % path,
                         level=error_level)
                return -1
        else:
            self.debug("mkdir_p: %s Already exists." % path)

    def rmtree(self, path, log_level=INFO, error_level=ERROR,
               exit_code=-1):
        """ Delete an entire directory tree and log its result.
        This method also logs the platform rmtree function, its retries, errors,
        and current existence of the directory.

        Args:
            path (str): path to the directory tree root to remove.
            log_level (str, optional): log level name to for this operation. Defaults
                                       to `INFO`.
            error_level (str, optional): log level name to use in case of error.
                                         Defaults to `ERROR`.
            exit_code (int, optional): useless parameter, not use here.
                                       Defaults to -1

        Returns:
            None: for success
        """

        self.log("rmtree: %s" % path, level=log_level)
        error_message = "Unable to remove %s!" % path
        if self._is_windows():
            # Call _rmtree_windows() directly, since even checking
            # os.path.exists(path) will hang if path is longer than MAX_PATH.
            self.info("Using _rmtree_windows ...")
            return self.retry(
                self._rmtree_windows,
                error_level=error_level,
                error_message=error_message,
                args=(path, ),
                log_level=log_level,
            )
        if os.path.exists(path):
            if os.path.isdir(path):
                return self.retry(
                    shutil.rmtree,
                    error_level=error_level,
                    error_message=error_message,
                    retry_exceptions=(OSError, ),
                    args=(path, ),
                    log_level=log_level,
                )
            else:
                return self.retry(
                    os.remove,
                    error_level=error_level,
                    error_message=error_message,
                    retry_exceptions=(OSError, ),
                    args=(path, ),
                    log_level=log_level,
                )
        else:
            self.debug("%s doesn't exist." % path)

    def query_msys_path(self, path):
        """ replaces the Windows harddrive letter path style with a linux
        path style, e.g. C:// --> /C/
        Note: method, not used in any script.

        Args:
            path (str?): path to convert to the linux path style.
        Returns:
            str: in case `path` is a string. The result is the path with the new notation.
            type(path): `path` itself is returned in case `path` is not str type.
        """
        if not isinstance(path, basestring):
            return path
        path = path.replace("\\", "/")

        def repl(m):
            return '/%s/' % m.group(1)
        path = re.sub(r'''^([a-zA-Z]):/''', repl, path)
        return path

    def _rmtree_windows(self, path):
        """ Windows-specific rmtree that handles path lengths longer than MAX_PATH.
            Ported from clobberer.py.

        Args:
            path (str): directory path to remove.

        Returns:
            None: if the path doesn't exists.
            int: the return number of calling `self.run_command`
            int: in case the path specified is not a directory but a file.
                 0 on success, non-zero on error. Note: The returned value
                 is the result of calling `win32file.DeleteFile`
        """

        assert self._is_windows()
        path = os.path.realpath(path)
        full_path = '\\\\?\\' + path
        if not os.path.exists(full_path):
            return
        if not PYWIN32:
            if not os.path.isdir(path):
                return self.run_command('del /F /Q "%s"' % path)
            else:
                return self.run_command('rmdir /S /Q "%s"' % path)
        # Make sure directory is writable
        win32file.SetFileAttributesW('\\\\?\\' + path, win32file.FILE_ATTRIBUTE_NORMAL)
        # Since we call rmtree() with a file, sometimes
        if not os.path.isdir('\\\\?\\' + path):
            return win32file.DeleteFile('\\\\?\\' + path)

        for ffrec in win32api.FindFiles('\\\\?\\' + path + '\\*.*'):
            file_attr = ffrec[0]
            name = ffrec[8]
            if name == '.' or name == '..':
                continue
            full_name = os.path.join(path, name)

            if file_attr & win32file.FILE_ATTRIBUTE_DIRECTORY:
                self._rmtree_windows(full_name)
            else:
                try:
                    win32file.SetFileAttributesW('\\\\?\\' + full_name, win32file.FILE_ATTRIBUTE_NORMAL)
                    win32file.DeleteFile('\\\\?\\' + full_name)
                except:
                    # DeleteFile fails on long paths, del /f /q works just fine
                    self.run_command('del /F /Q "%s"' % full_name)

        win32file.RemoveDirectory('\\\\?\\' + path)

    def get_filename_from_url(self, url):
        """ parse a filename base on an url.

        Args:
            url (str): url to parse for the filename

        Returns:
            str: filename parsed from the url, or `netloc` network location part
                 of the url.
        """

        parsed = urlparse.urlsplit(url.rstrip('/'))
        if parsed.path != '':
            return parsed.path.rsplit('/', 1)[-1]
        else:
            return parsed.netloc

    def _urlopen(self, url, **kwargs):
        """ open the url `url` using `urllib2`.
        This method can be overwritten to extend its complexity

        Args:
            url (str | urllib2.Request): url to open
            kwargs: Arbitrary keyword arguments passed to the `urllib2.urlopen` function.

        Returns:
            file-like: file-like object with additional methods as defined in
                       `urllib2.urlopen`_.
            None: None may be returned if no handler handles the request.

        Raises:
            urllib2.URLError: on errors

        .. _urllib2.urlopen:
        https://docs.python.org/2/library/urllib2.html#urllib2.urlopen
        """
        # http://bugs.python.org/issue13359 - urllib2 does not automatically quote the URL
        url_quoted = urllib2.quote(url, safe='%/:=&?~#+!$,;\'@()*[]|')
        return urllib2.urlopen(url_quoted, **kwargs)



    def fetch_url_into_memory(self, url):
        ''' Downloads a file from a url into memory instead of disk.

        Args:
            url (str): URL path where the file to be downloaded is located.

        Raises:
            IOError: When the url points to a file on disk and cannot be found
            ContentLengthMismatch: When the length of the retrieved content does not match the
                                   Content-Length response header.
            ValueError: When the scheme of a url is not what is expected.

        Returns:
            BytesIO: contents of url
        '''
        self.info('Fetch {} into memory'.format(url))
        parsed_url = urlparse.urlparse(url)

        if parsed_url.scheme in ('', 'file'):
            path = parsed_url.path
            if not os.path.isfile(path):
                raise IOError('Could not find file to extract: {}'.format(url))

            content_length = os.stat(path).st_size

            # In case we're referrencing a file without file://
            if parsed_url.scheme == '':
                url = 'file://%s' % os.path.abspath(url)
                parsed_url = urlparse.urlparse(url)

        request = urllib2.Request(url)
        # When calling fetch_url_into_memory() you should retry when we raise one of these exceptions:
        # * Bug 1300663 - HTTPError: HTTP Error 404: Not Found
        # * Bug 1300413 - HTTPError: HTTP Error 500: Internal Server Error
        # * Bug 1300943 - HTTPError: HTTP Error 503: Service Unavailable
        # * Bug 1300953 - URLError: <urlopen error [Errno -2] Name or service not known>
        # * Bug 1301594 - URLError: <urlopen error [Errno 10054] An existing connection was ...
        # * Bug 1301597 - URLError: <urlopen error [Errno 8] _ssl.c:504: EOF occurred in ...
        # * Bug 1301855 - URLError: <urlopen error [Errno 60] Operation timed out>
        # * Bug 1302237 - URLError: <urlopen error [Errno 104] Connection reset by peer>
        # * Bug 1301807 - BadStatusLine: ''
        #
        # Bug 1309912 - Adding timeout in hopes to solve blocking on response.read() (bug 1300413)
        response = urllib2.urlopen(request, timeout=30)

        if parsed_url.scheme in ('http', 'https'):
            content_length = int(response.headers.get('Content-Length'))

        response_body = response.read()
        response_body_size = len(response_body)

        self.info('Content-Length response header: {}'.format(content_length))
        self.info('Bytes received: {}'.format(response_body_size))

        if response_body_size != content_length:
            raise ContentLengthMismatch(
                'The retrieved Content-Length header declares a body length of {} bytes, while we actually retrieved {} bytes'.format(
                    content_length, response_body_size)
            )

        if response.info().get('Content-Encoding') == 'gzip':
            self.info('Content-Encoding is "gzip", so decompressing response body')
            # See http://www.zlib.net/manual.html#Advanced
            # section "ZEXTERN int ZEXPORT inflateInit2 OF....":
            #   Add 32 to windowBits to enable zlib and gzip decoding with automatic
            #   header detection, or add 16 to decode only the gzip format (the zlib
            #   format will return a Z_DATA_ERROR).
            # Adding 16 since we only wish to support gzip encoding.
            file_contents = zlib.decompress(response_body, zlib.MAX_WBITS|16)
        else:
            file_contents = response_body

        # Use BytesIO instead of StringIO
        # http://stackoverflow.com/questions/34162017/unzip-buffer-with-python/34162395#34162395
        return BytesIO(file_contents)


    def _download_file(self, url, file_name):
        """ Helper function for download_file()
        Additionaly this function logs all exceptions as warnings before
        re-raising them

        Args:
            url (str): string containing the URL with the file location
            file_name (str): name of the file where the downloaded file
                             is written.

        Returns:
            str: filename of the written file on disk

        Raises:
            urllib2.URLError: on incomplete download.
            urllib2.HTTPError: on Http error code
            socket.timeout: on connection timeout
            socket.error: on socket error
        """
        # If our URLs look like files, prefix them with file:// so they can
        # be loaded like URLs.
        if not (url.startswith("http") or url.startswith("file://")):
            if not os.path.isfile(url):
                self.fatal("The file %s does not exist" % url)
            url = 'file://%s' % os.path.abspath(url)

        try:
            f_length = None
            f = self._urlopen(url, timeout=30)

            if f.info().get('content-length') is not None:
                f_length = int(f.info()['content-length'])
                got_length = 0
            if f.info().get('Content-Encoding') == 'gzip':
                # Note, we'll download the full compressed content into its own
                # file, since that allows the gzip library to seek through it.
                # Once downloaded, we'll decompress it into the real target
                # file, and delete the compressed version.
                local_file = open(file_name + '.gz', 'wb')
            else:
                local_file = open(file_name, 'wb')
            while True:
                block = f.read(1024 ** 2)
                if not block:
                    if f_length is not None and got_length != f_length:
                        raise urllib2.URLError("Download incomplete; content-length was %d, but only received %d" % (f_length, got_length))
                    break
                local_file.write(block)
                if f_length is not None:
                    got_length += len(block)
            local_file.close()
            if f.info().get('Content-Encoding') == 'gzip':
                # Decompress file into target location, then remove compressed version
                with open(file_name, 'wb') as f_out:
                    # On some execution paths, this could be called with python 2.6
                    # whereby gzip.open(...) cannot be used with a 'with' statement.
                    # So let's do this the python 2.6 way...
                    try:
                        f_in = gzip.open(file_name + '.gz', 'rb')
                        shutil.copyfileobj(f_in, f_out)
                    finally:
                        f_in.close()
                os.remove(file_name + '.gz')
            return file_name
        except urllib2.HTTPError, e:
            self.warning("Server returned status %s %s for %s" % (str(e.code), str(e), url))
            raise
        except urllib2.URLError, e:
            self.warning("URL Error: %s" % url)

            # Failures due to missing local files won't benefit from retry.
            # Raise the original OSError.
            if isinstance(e.args[0], OSError) and e.args[0].errno == errno.ENOENT:
                raise e.args[0]

            remote_host = urlparse.urlsplit(url)[1]
            if remote_host:
                nslookup = self.query_exe('nslookup')
                error_list = [{
                    'substr': "server can't find %s" % remote_host,
                    'level': ERROR,
                    'explanation': "Either %s is an invalid hostname, or DNS is busted." % remote_host,
                }]
                self.run_command([nslookup, remote_host],
                                 error_list=error_list)
            raise
        except socket.timeout, e:
            self.warning("Timed out accessing %s: %s" % (url, str(e)))
            raise
        except socket.error, e:
            self.warning("Socket error when accessing %s: %s" % (url, str(e)))
            raise

    def _retry_download(self, url, error_level, file_name=None, retry_config=None):
        """ Helper method to retry download methods.

        This method calls `self.retry` on `self._download_file` using the passed
        parameters if a file_name is specified. If no file is specified, we will
        instead call `self._urlopen`, which grabs the contents of a url but does
        not create a file on disk.

        Args:
            url (str): URL path where the file is located.
            file_name (str): file_name where the file will be written to.
            error_level (str): log level to use in case an error occurs.
            retry_config (dict, optional): key-value pairs to be passed to
                                           `self.retry`. Defaults to `None`

        Returns:
            str: `self._download_file` return value is returned
            unknown: `self.retry` `failure_status` is returned on failure, which
                     defaults to -1
        """
        retry_args = dict(
            failure_status=None,
            retry_exceptions=(urllib2.HTTPError, urllib2.URLError,
                              httplib.BadStatusLine,
                              socket.timeout, socket.error),
            error_message="Can't download from %s to %s!" % (url, file_name),
            error_level=error_level,
        )

        if retry_config:
            retry_args.update(retry_config)

        download_func = self._urlopen
        kwargs = {"url": url}
        if file_name:
            download_func = self._download_file
            kwargs = {"url": url, "file_name": file_name}

        return self.retry(
            download_func,
            kwargs=kwargs,
            **retry_args
        )


    def _filter_entries(self, namelist, extract_dirs):
        """Filter entries of the archive based on the specified list of to extract dirs."""
        filter_partial = functools.partial(fnmatch.filter, namelist)
        entries = itertools.chain(*map(filter_partial, extract_dirs or ['*']))

        for entry in entries:
            yield entry


    def unzip(self, compressed_file, extract_to, extract_dirs='*', verbose=False):
        """This method allows to extract a zip file without writing to disk first.

        Args:
            compressed_file (object): File-like object with the contents of a compressed zip file.
            extract_to (str): where to extract the compressed file.
            extract_dirs (list, optional): directories inside the archive file to extract.
                                           Defaults to '*'.
            verbose (bool, optional): whether or not extracted content should be displayed.
                                      Defaults to False.

        Raises:
            zipfile.BadZipfile: on contents of zipfile being invalid
        """
        with zipfile.ZipFile(compressed_file) as bundle:
            entries = self._filter_entries(bundle.namelist(), extract_dirs)

            for entry in entries:
                if verbose:
                    self.info(' {}'.format(entry))

                # Exception to be retried:
                # Bug 1301645 - BadZipfile: Bad CRC-32 for file ...
                #    http://stackoverflow.com/questions/5624669/strange-badzipfile-bad-crc-32-problem/5626098#5626098
                # Bug 1301802 - error: Error -3 while decompressing: invalid stored block lengths
                bundle.extract(entry, path=extract_to)

                # ZipFile doesn't preserve permissions during extraction:
                # http://bugs.python.org/issue15795
                fname = os.path.realpath(os.path.join(extract_to, entry))
                try:
                    # getinfo() can raise KeyError
                    mode = bundle.getinfo(entry).external_attr >> 16 & 0x1FF
                    # Only set permissions if attributes are available. Otherwise all
                    # permissions will be removed eg. on Windows.
                    if mode:
                        os.chmod(fname, mode)

                except KeyError:
                    self.warning('{} was not found in the zip file'.format(entry))


    def deflate(self, compressed_file, mode, extract_to='.', *args, **kwargs):
        """This method allows to extract a compressed file from a tar, tar.bz2 and tar.gz files.

        Args:
            compressed_file (object): File-like object with the contents of a compressed file.
            mode (str): string of the form 'filemode[:compression]' (e.g. 'r:gz' or 'r:bz2')
            extract_to (str, optional): where to extract the compressed file.
        """
        t = tarfile.open(fileobj=compressed_file, mode=mode)
        t.extractall(path=extract_to)


    def download_unpack(self, url, extract_to='.', extract_dirs='*', verbose=False):
        """Generic method to download and extract a compressed file without writing it to disk first.

        Args:
            url (str): URL where the file to be downloaded is located.
            extract_to (str, optional): directory where the downloaded file will
                                        be extracted to.
            extract_dirs (list, optional): directories inside the archive to extract.
                                           Defaults to `*`. It currently only applies to zip files.
            verbose (bool, optional): whether or not extracted content should be displayed.
                                      Defaults to False.

        """
        def _determine_extraction_method_and_kwargs(url):
            EXTENSION_TO_MIMETYPE = {
                'bz2': 'application/x-bzip2',
                'gz':  'application/x-gzip',
                'tar': 'application/x-tar',
                'zip': 'application/zip',
            }
            MIMETYPES = {
                'application/x-bzip2': {
                    'function': self.deflate,
                    'kwargs': {'mode': 'r:bz2'},
                },
                'application/x-gzip': {
                    'function': self.deflate,
                    'kwargs': {'mode': 'r:gz'},
                },
                'application/x-tar': {
                    'function': self.deflate,
                    'kwargs': {'mode': 'r'},
                },
                'application/zip': {
                    'function': self.unzip,
                },
                'application/x-zip-compressed': {
                    'function': self.unzip,
                },
            }

            filename = url.split('/')[-1]
            # XXX: bz2/gz instead of tar.{bz2/gz}
            extension = filename[filename.rfind('.')+1:]
            mimetype = EXTENSION_TO_MIMETYPE[extension]
            self.debug('Mimetype: {}'.format(mimetype))

            function = MIMETYPES[mimetype]['function']
            kwargs = {
                'compressed_file': compressed_file,
                'extract_to': extract_to,
                'extract_dirs': extract_dirs,
                'verbose': verbose,
            }
            kwargs.update(MIMETYPES[mimetype].get('kwargs', {}))

            return function, kwargs

        # Many scripts overwrite this method and set extract_dirs to None
        extract_dirs = '*' if extract_dirs is None else extract_dirs
        self.info('Downloading and extracting to {} these dirs {} from {}'.format(
            extract_to,
            ', '.join(extract_dirs),
            url,
        ))

        # 1) Let's fetch the file
        retry_args = dict(
            retry_exceptions=(
                urllib2.HTTPError,
                urllib2.URLError,
                httplib.BadStatusLine,
                socket.timeout,
                socket.error,
                ContentLengthMismatch,
            ),
            sleeptime=30,
            attempts=5,
            error_message="Can't download from {}".format(url),
            error_level=FATAL,
        )
        compressed_file = self.retry(
            self.fetch_url_into_memory,
            kwargs={'url': url},
            **retry_args
        )

        # 2) We're guaranteed to have download the file with error_level=FATAL
        #    Let's unpack the file
        function, kwargs = _determine_extraction_method_and_kwargs(url)
        try:
            function(**kwargs)
        except zipfile.BadZipfile:
            # Dump the exception and exit
            self.exception(level=FATAL)


    def load_json_url(self, url, error_level=None, *args, **kwargs):
        """ Returns a json object from a url (it retries). """
        contents = self._retry_download(
            url=url, error_level=error_level, *args, **kwargs
        )
        return json.loads(contents.read())

    # http://www.techniqal.com/blog/2008/07/31/python-file-read-write-with-urllib2/
    # TODO thinking about creating a transfer object.
    def download_file(self, url, file_name=None, parent_dir=None,
                      create_parent_dir=True, error_level=ERROR,
                      exit_code=3, retry_config=None):
        """ Python wget.
        Download the filename at `url` into `file_name` and put it on `parent_dir`.
        On error log with the specified `error_level`, on fatal exit with `exit_code`.
        Execute all the above based on `retry_config` parameter.

        Args:
            url (str): URL path where the file to be downloaded is located.
            file_name (str, optional): file_name where the file will be written to.
                                       Defaults to urls' filename.
            parent_dir (str, optional): directory where the downloaded file will
                                        be written to. Defaults to current working
                                        directory
            create_parent_dir (bool, optional): create the parent directory if it
                                                doesn't exist. Defaults to `True`
            error_level (str, optional): log level to use in case an error occurs.
                                         Defaults to `ERROR`
            retry_config (dict, optional): key-value pairs to be passed to
                                          `self.retry`. Defaults to `None`

        Returns:
            str: filename where the downloaded file was written to.
            unknown: on failure, `failure_status` is returned.
        """
        if not file_name:
            try:
                file_name = self.get_filename_from_url(url)
            except AttributeError:
                self.log("Unable to get filename from %s; bad url?" % url,
                         level=error_level, exit_code=exit_code)
                return
        if parent_dir:
            file_name = os.path.join(parent_dir, file_name)
            if create_parent_dir:
                self.mkdir_p(parent_dir, error_level=error_level)
        self.info("Downloading %s to %s" % (url, file_name))
        status = self._retry_download(
            url=url,
            error_level=error_level,
            file_name=file_name,
            retry_config=retry_config
        )
        if status == file_name:
            self.info("Downloaded %d bytes." % os.path.getsize(file_name))
        return status

    def move(self, src, dest, log_level=INFO, error_level=ERROR,
             exit_code=-1):
        """ recursively move a file or directory (src) to another location (dest).

        Args:
            src (str): file or directory path to move.
            dest (str): file or directory path where to move the content to.
            log_level (str): log level to use for normal operation. Defaults to
                                `INFO`
            error_level (str): log level to use on error. Defaults to `ERROR`

        Returns:
            int: 0 on success. -1 on error.
        """
        self.log("Moving %s to %s" % (src, dest), level=log_level)
        try:
            shutil.move(src, dest)
        # http://docs.python.org/tutorial/errors.html
        except IOError, e:
            self.log("IO error: %s" % str(e),
                     level=error_level, exit_code=exit_code)
            return -1
        except shutil.Error, e:
            self.log("shutil error: %s" % str(e),
                     level=error_level, exit_code=exit_code)
            return -1
        return 0

    def chmod(self, path, mode):
        """ change `path` mode to `mode`.

        Args:
            path (str): path whose mode will be modified.
            mode (hex): one of the values defined at `stat`_

        .. _stat:
        https://docs.python.org/2/library/os.html#os.chmod
        """

        self.info("Chmoding %s to %s" % (path, str(oct(mode))))
        os.chmod(path, mode)

    def copyfile(self, src, dest, log_level=INFO, error_level=ERROR, copystat=False, compress=False):
        """ copy or compress `src` into `dest`.

        Args:
            src (str): filepath to copy.
            dest (str): filepath where to move the content to.
            log_level (str, optional): log level to use for normal operation. Defaults to
                                      `INFO`
            error_level (str, optional): log level to use on error. Defaults to `ERROR`
            copystat (bool, optional): whether or not to copy the files metadata.
                                       Defaults to `False`.
            compress (bool, optional): whether or not to compress the destination file.
                                       Defaults to `False`.

        Returns:
            int: -1 on error
            None: on success
        """

        if compress:
            self.log("Compressing %s to %s" % (src, dest), level=log_level)
            try:
                infile = open(src, "rb")
                outfile = gzip.open(dest, "wb")
                outfile.writelines(infile)
                outfile.close()
                infile.close()
            except IOError, e:
                self.log("Can't compress %s to %s: %s!" % (src, dest, str(e)),
                         level=error_level)
                return -1
        else:
            self.log("Copying %s to %s" % (src, dest), level=log_level)
            try:
                shutil.copyfile(src, dest)
            except (IOError, shutil.Error), e:
                self.log("Can't copy %s to %s: %s!" % (src, dest, str(e)),
                         level=error_level)
                return -1

        if copystat:
            try:
                shutil.copystat(src, dest)
            except (IOError, shutil.Error), e:
                self.log("Can't copy attributes of %s to %s: %s!" % (src, dest, str(e)),
                         level=error_level)
                return -1

    def copytree(self, src, dest, overwrite='no_overwrite', log_level=INFO,
                 error_level=ERROR):
        """ An implementation of `shutil.copytree` that allows for `dest` to exist
        and implements different overwrite levels:
        - 'no_overwrite' will keep all(any) existing files in destination tree
        - 'overwrite_if_exists' will only overwrite destination paths that have
                                the same path names relative to the root of the
                                src and destination tree
        - 'clobber' will replace the whole destination tree(clobber) if it exists

        Args:
            src (str): directory path to move.
            dest (str): directory path where to move the content to.
            overwrite (str): string specifying the overwrite level.
            log_level (str, optional): log level to use for normal operation. Defaults to
                                      `INFO`
            error_level (str, optional): log level to use on error. Defaults to `ERROR`

        Returns:
            int: -1 on error
            None: on success
        """

        self.info('copying tree: %s to %s' % (src, dest))
        try:
            if overwrite == 'clobber' or not os.path.exists(dest):
                self.rmtree(dest)
                shutil.copytree(src, dest)
            elif overwrite == 'no_overwrite' or overwrite == 'overwrite_if_exists':
                files = os.listdir(src)
                for f in files:
                    abs_src_f = os.path.join(src, f)
                    abs_dest_f = os.path.join(dest, f)
                    if not os.path.exists(abs_dest_f):
                        if os.path.isdir(abs_src_f):
                            self.mkdir_p(abs_dest_f)
                            self.copytree(abs_src_f, abs_dest_f,
                                          overwrite='clobber')
                        else:
                            shutil.copy2(abs_src_f, abs_dest_f)
                    elif overwrite == 'no_overwrite':  # destination path exists
                        if os.path.isdir(abs_src_f) and os.path.isdir(abs_dest_f):
                            self.copytree(abs_src_f, abs_dest_f,
                                          overwrite='no_overwrite')
                        else:
                            self.debug('ignoring path: %s as destination: \
                                    %s exists' % (abs_src_f, abs_dest_f))
                    else:  # overwrite == 'overwrite_if_exists' and destination exists
                        self.debug('overwriting: %s with: %s' %
                                   (abs_dest_f, abs_src_f))
                        self.rmtree(abs_dest_f)

                        if os.path.isdir(abs_src_f):
                            self.mkdir_p(abs_dest_f)
                            self.copytree(abs_src_f, abs_dest_f,
                                          overwrite='overwrite_if_exists')
                        else:
                            shutil.copy2(abs_src_f, abs_dest_f)
            else:
                self.fatal("%s is not a valid argument for param overwrite" % (overwrite))
        except (IOError, shutil.Error):
            self.exception("There was an error while copying %s to %s!" % (src, dest),
                           level=error_level)
            return -1

    def write_to_file(self, file_path, contents, verbose=True,
                      open_mode='w', create_parent_dir=False,
                      error_level=ERROR):
        """ Write `contents` to `file_path`, according to `open_mode`.

        Args:
            file_path (str): filepath where the content will be written to.
            contents (str): content to write to the filepath.
            verbose (bool, optional): whether or not to log `contents` value.
                                      Defaults to `True`
            open_mode (str, optional): open mode to use for openning the file.
                                       Defaults to `w`
            create_parent_dir (bool, optional): whether or not to create the
                                                parent directory of `file_path`
            error_level (str, optional): log level to use on error. Defaults to `ERROR`

        Returns:
            str: `file_path` on success
            None: on error.
        """
        self.info("Writing to file %s" % file_path)
        if verbose:
            self.info("Contents:")
            for line in contents.splitlines():
                self.info(" %s" % line)
        if create_parent_dir:
            parent_dir = os.path.dirname(file_path)
            self.mkdir_p(parent_dir, error_level=error_level)
        try:
            fh = open(file_path, open_mode)
            try:
                fh.write(contents)
            except UnicodeEncodeError:
                fh.write(contents.encode('utf-8', 'replace'))
            fh.close()
            return file_path
        except IOError:
            self.log("%s can't be opened for writing!" % file_path,
                     level=error_level)

    @contextmanager
    def opened(self, file_path, verbose=True, open_mode='r',
               error_level=ERROR):
        """ Create a context manager to use on a with statement.

        Args:
            file_path (str): filepath of the file to open.
            verbose (bool, optional): useless parameter, not used here.
                Defaults to True.
            open_mode (str, optional): open mode to use for openning the file.
                Defaults to `r`
            error_level (str, optional): log level name to use on error.
                Defaults to `ERROR`

        Yields:
            tuple: (file object, error) pair. In case of error `None` is yielded
                as file object, together with the corresponding error.
                If there is no error, `None` is returned as the error.
        """
        # See opened_w_error in http://www.python.org/dev/peps/pep-0343/
        self.info("Reading from file %s" % file_path)
        try:
            fh = open(file_path, open_mode)
        except IOError, err:
            self.log("unable to open %s: %s" % (file_path, err.strerror),
                     level=error_level)
            yield None, err
        else:
            try:
                yield fh, None
            finally:
                fh.close()

    def read_from_file(self, file_path, verbose=True, open_mode='r',
                       error_level=ERROR):
        """ Use `self.opened` context manager to open a file and read its
        content.

        Args:
            file_path (str): filepath of the file to read.
            verbose (bool, optional): whether or not to log the file content.
                Defaults to True.
            open_mode (str, optional): open mode to use for openning the file.
                Defaults to `r`
            error_level (str, optional): log level name to use on error.
                Defaults to `ERROR`

        Returns:
            None: on error.
            str: file content on success.
        """
        with self.opened(file_path, verbose, open_mode, error_level) as (fh, err):
            if err:
                return None
            contents = fh.read()
            if verbose:
                self.info("Contents:")
                for line in contents.splitlines():
                    self.info(" %s" % line)
            return contents

    def chdir(self, dir_name):
        self.log("Changing directory to %s." % dir_name)
        os.chdir(dir_name)

    def is_exe(self, fpath):
        """
        Determine if fpath is a file and if it is executable.
        """
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    def which(self, program):
        """ OS independent implementation of Unix's which command

        Args:
            program (str): name or path to the program whose executable is
                being searched.

        Returns:
            None: if the executable was not found.
            str: filepath of the executable file.
        """
        if self._is_windows() and not program.endswith(".exe"):
            program += ".exe"
        fpath, fname = os.path.split(program)
        if fpath:
            if self.is_exe(program):
                return program
        else:
            # If the exe file is defined in the configs let's use that
            exe = self.query_exe(program)
            if self.is_exe(exe):
                return exe

            # If not defined, let's look for it in the $PATH
            env = self.query_env()
            for path in env["PATH"].split(os.pathsep):
                exe_file = os.path.join(path, program)
                if self.is_exe(exe_file):
                    return exe_file
        return None

    # More complex commands {{{2
    def retry(self, action, attempts=None, sleeptime=60, max_sleeptime=5 * 60,
              retry_exceptions=(Exception, ), good_statuses=None, cleanup=None,
              error_level=ERROR, error_message="%(action)s failed after %(attempts)d tries!",
              failure_status=-1, log_level=INFO, args=(), kwargs={}):
        """ generic retry command. Ported from `util.retry`_

        Args:
            action (func): callable object to retry.
            attempts (int, optinal): maximum number of times to call actions.
                Defaults to `self.config.get('global_retries', 5)`
            sleeptime (int, optional): number of seconds to wait between
                attempts. Defaults to 60 and doubles each retry attempt, to
                a maximum of `max_sleeptime'
            max_sleeptime (int, optional): maximum value of sleeptime. Defaults
                to 5 minutes
            retry_exceptions (tuple, optional): Exceptions that should be caught.
                If exceptions other than those listed in `retry_exceptions' are
                raised from `action', they will be raised immediately. Defaults
                to (Exception)
            good_statuses (object, optional): return values which, if specified,
                will result in retrying if the return value isn't listed.
                Defaults to `None`.
            cleanup (func, optional): If `cleanup' is provided and callable
                it will be called immediately after an Exception is caught.
                No arguments will be passed to it. If your cleanup function
                requires arguments it is recommended that you wrap it in an
                argumentless function.
                Defaults to `None`.
            error_level (str, optional): log level name in case of error.
                Defaults to `ERROR`.
            error_message (str, optional): string format to use in case
                none of the attempts success. Defaults to
                '%(action)s failed after %(attempts)d tries!'
            failure_status (int, optional): flag to return in case the retries
                were not successfull. Defaults to -1.
            log_level (str, optional): log level name to use for normal activity.
                Defaults to `INFO`.
            args (tuple, optional): positional arguments to pass onto `action`.
            kwargs (dict, optional): key-value arguments to pass onto `action`.

        Returns:
            object: return value of `action`.
            int: failure status in case of failure retries.
        """
        if not callable(action):
            self.fatal("retry() called with an uncallable method %s!" % action)
        if cleanup and not callable(cleanup):
            self.fatal("retry() called with an uncallable cleanup method %s!" % cleanup)
        if not attempts:
            attempts = self.config.get("global_retries", 5)
        if max_sleeptime < sleeptime:
            self.debug("max_sleeptime %d less than sleeptime %d" % (
                       max_sleeptime, sleeptime))
        n = 0
        while n <= attempts:
            retry = False
            n += 1
            try:
                self.log("retry: Calling %s with args: %s, kwargs: %s, attempt #%d" %
                         (action.__name__, str(args), str(kwargs), n), level=log_level)
                status = action(*args, **kwargs)
                if good_statuses and status not in good_statuses:
                    retry = True
            except retry_exceptions, e:
                retry = True
                error_message = "%s\nCaught exception: %s" % (error_message, str(e))
                self.log('retry: attempt #%d caught %s exception: %s' %
                         (n, type(e).__name__, str(e)), level=INFO)

            if not retry:
                return status
            else:
                if cleanup:
                    cleanup()
                if n == attempts:
                    self.log(error_message % {'action': action, 'attempts': n}, level=error_level)
                    return failure_status
                if sleeptime > 0:
                    self.log("retry: Failed, sleeping %d seconds before retrying" %
                             sleeptime, level=log_level)
                    time.sleep(sleeptime)
                    sleeptime = sleeptime * 2
                    if sleeptime > max_sleeptime:
                        sleeptime = max_sleeptime

    def query_env(self, partial_env=None, replace_dict=None,
                  purge_env=(),
                  set_self_env=None, log_level=DEBUG,
                  avoid_host_env=False):
        """ Environment query/generation method.
        The default, self.query_env(), will look for self.config['env']
        and replace any special strings in there ( %(PATH)s ).
        It will then store it as self.env for speeding things up later.

        If you specify partial_env, partial_env will be used instead of
        self.config['env'], and we don't save self.env as it's a one-off.


        Args:
            partial_env (dict, optional): key-value pairs of the name and value
                of different environment variables. Defaults to an empty dictionary.
            replace_dict (dict, optional): key-value pairs to replace the old
                environment variables.
            purge_env (list): environment names to delete from the final
                environment dictionary.
            set_self_env (boolean, optional): whether or not the environment
                variables dictionary should be copied to `self`.
                Defaults to True.
            log_level (str, optional): log level name to use on normal operation.
                Defaults to `DEBUG`.
            avoid_host_env (boolean, optional): if set to True, we will not use
                any environment variables set on the host except PATH.
                Defaults to False.

        Returns:
            dict: environment variables names with their values.
        """
        if partial_env is None:
            if self.env is not None:
                return self.env
            partial_env = self.config.get('env', None)
            if partial_env is None:
                partial_env = {}
            if set_self_env is None:
                set_self_env = True

        env = {'PATH': os.environ['PATH']} if avoid_host_env else os.environ.copy()

        default_replace_dict = self.query_abs_dirs()
        default_replace_dict['PATH'] = os.environ['PATH']
        if not replace_dict:
            replace_dict = default_replace_dict
        else:
            for key in default_replace_dict:
                if key not in replace_dict:
                    replace_dict[key] = default_replace_dict[key]
        for key in partial_env.keys():
            env[key] = partial_env[key] % replace_dict
            self.log("ENV: %s is now %s" % (key, env[key]), level=log_level)
        for k in purge_env:
            if k in env:
                del env[k]
        if set_self_env:
            self.env = env
        return env

    def query_exe(self, exe_name, exe_dict='exes', default=None,
                  return_type=None, error_level=FATAL):
        """One way to work around PATH rewrites.

        By default, return exe_name, and we'll fall through to searching
        os.environ["PATH"].
        However, if self.config[exe_dict][exe_name] exists, return that.
        This lets us override exe paths via config file.

        If we need runtime setting, we can build in self.exes support later.

        Args:
            exe_name (str): name of the executable to search for.
            exe_dict(str, optional): name of the dictionary of executables
              present in `self.config`. Defaults to `exes`.
            default (str, optional): default name of the executable to search
              for. Defaults to `exe_name`.
            return_type (str, optional): type to which the original return
              value will be turn into. Only 'list', 'string' and `None` are
              supported. Defaults to `None`.
            error_level (str, optional): log level name to use on error.

        Returns:
            list: in case return_type is 'list'
            str: in case return_type is 'string'
            None: in case return_type is `None`
            Any: if the found executable is not of type list, tuple nor str.
        """
        if default is None:
            default = exe_name
        exe = self.config.get(exe_dict, {}).get(exe_name, default)
        repl_dict = {}
        if hasattr(self.script_obj, 'query_abs_dirs'):
            # allow for 'make': '%(abs_work_dir)s/...' etc.
            dirs = self.script_obj.query_abs_dirs()
            repl_dict.update(dirs)
        if isinstance(exe, dict):
            found = False
            # allow for searchable paths of the buildbot exe
            for name, path in exe.iteritems():
                if isinstance(path, list) or isinstance(path, tuple):
                    path = [x % repl_dict for x in path]
                    if all([os.path.exists(section) for section in path]):
                        found = True
                elif isinstance(path, str):
                    path = path % repl_dict
                    if os.path.exists(path):
                        found = True
                else:
                    self.log("a exes %s dict's value is not a string, list, or tuple. Got key "
                             "%s and value %s" % (exe_name, name, str(path)), level=error_level)
                if found:
                    exe = path
                    break
            else:
                self.log("query_exe was a searchable dict but an existing path could not be "
                         "determined. Tried searching in paths: %s" % (str(exe)), level=error_level)
                return None
        elif isinstance(exe, list) or isinstance(exe, tuple):
            exe = [x % repl_dict for x in exe]
        elif isinstance(exe, str):
            exe = exe % repl_dict
        else:
            self.log("query_exe: %s is not a list, tuple, dict, or string: "
                     "%s!" % (exe_name, str(exe)), level=error_level)
            return exe
        if return_type == "list":
            if isinstance(exe, str):
                exe = [exe]
        elif return_type == "string":
            if isinstance(exe, list):
                exe = subprocess.list2cmdline(exe)
        elif return_type is not None:
            self.log("Unknown return_type type %s requested in query_exe!" % return_type, level=error_level)
        return exe

    def run_command(self, command, cwd=None, error_list=None,
                    halt_on_failure=False, success_codes=None,
                    env=None, partial_env=None, return_type='status',
                    throw_exception=False, output_parser=None,
                    output_timeout=None, fatal_exit_code=2,
                    error_level=ERROR, **kwargs):
        """Run a command, with logging and error parsing.
        TODO: context_lines

        error_list example:
        [{'regex': re.compile('^Error: LOL J/K'), level=IGNORE},
         {'regex': re.compile('^Error:'), level=ERROR, contextLines='5:5'},
         {'substr': 'THE WORLD IS ENDING', level=FATAL, contextLines='20:'}
        ]
        (context_lines isn't written yet)

        Args:
            command (str | list | tuple): command or sequence of commands to
              execute and log.
            cwd (str, optional): directory path from where to execute the
              command. Defaults to `None`.
            error_list (list, optional): list of errors to pass to
              `mozharness.base.log.OutputParser`. Defaults to `None`.
            halt_on_failure (bool, optional): whether or not to redefine the
              log level as `FATAL` on errors. Defaults to False.
            success_codes (int, optional): numeric value to compare against
              the command return value.
            env (dict, optional): key-value of environment values to use to
              run the command. Defaults to None.
            partial_env (dict, optional): key-value of environment values to
              replace from the current environment values. Defaults to None.
            return_type (str, optional): if equal to 'num_errors' then the
              amount of errors matched by `error_list` is returned. Defaults
              to 'status'.
            throw_exception (bool, optional): whether or not to raise an
              exception if the return value of the command doesn't match
              any of the `success_codes`. Defaults to False.
            output_parser (OutputParser, optional): lets you provide an
              instance of your own OutputParser subclass. Defaults to `OutputParser`.
            output_timeout (int): amount of seconds to wait for output before
              the process is killed.
            fatal_exit_code (int, optional): call `self.fatal` if the return value
              of the command is not in `success_codes`. Defaults to 2.
            error_level (str, optional): log level name to use on error. Defaults
              to `ERROR`.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            int: -1 on error.
            Any: `command` return value is returned otherwise.
        """
        if success_codes is None:
            success_codes = [0]
        if cwd is not None:
            if not os.path.isdir(cwd):
                level = error_level
                if halt_on_failure:
                    level = FATAL
                self.log("Can't run command %s in non-existent directory '%s'!" %
                         (command, cwd), level=level)
                return -1
            self.info("Running command: %s in %s" % (command, cwd))
        else:
            self.info("Running command: %s" % command)
        if isinstance(command, list) or isinstance(command, tuple):
            self.info("Copy/paste: %s" % subprocess.list2cmdline(command))
        shell = True
        if isinstance(command, list) or isinstance(command, tuple):
            shell = False
        if env is None:
            if partial_env:
                self.info("Using partial env: %s" % pprint.pformat(partial_env))
                env = self.query_env(partial_env=partial_env)
        else:
            self.info("Using env: %s" % pprint.pformat(env))

        if output_parser is None:
            parser = OutputParser(config=self.config, log_obj=self.log_obj,
                                  error_list=error_list)
        else:
            parser = output_parser

        try:
            if output_timeout:
                def processOutput(line):
                    parser.add_lines(line)

                def onTimeout():
                    self.info("Automation Error: mozprocess timed out after %s seconds running %s" % (str(output_timeout), str(command)))

                p = ProcessHandler(command,
                                   shell=shell,
                                   env=env,
                                   cwd=cwd,
                                   storeOutput=False,
                                   onTimeout=(onTimeout,),
                                   processOutputLine=[processOutput])
                self.info("Calling %s with output_timeout %d" % (command, output_timeout))
                p.run(outputTimeout=output_timeout)
                p.wait()
                if p.timedOut:
                    self.log(
                        'timed out after %s seconds of no output' % output_timeout,
                        level=error_level
                    )
                returncode = int(p.proc.returncode)
            else:
                p = subprocess.Popen(command, shell=shell, stdout=subprocess.PIPE,
                                     cwd=cwd, stderr=subprocess.STDOUT, env=env,
                                     bufsize=0)
                loop = True
                while loop:
                    if p.poll() is not None:
                        """Avoid losing the final lines of the log?"""
                        loop = False
                    while True:
                        line = p.stdout.readline()
                        if not line:
                            break
                        parser.add_lines(line)
                returncode = p.returncode
        except OSError, e:
            level = error_level
            if halt_on_failure:
                level = FATAL
            self.log('caught OS error %s: %s while running %s' % (e.errno,
                     e.strerror, command), level=level)
            return -1

        return_level = INFO
        if returncode not in success_codes:
            return_level = error_level
            if throw_exception:
                raise subprocess.CalledProcessError(returncode, command)
        self.log("Return code: %d" % returncode, level=return_level)

        if halt_on_failure:
            _fail = False
            if returncode not in success_codes:
                self.log(
                    "%s not in success codes: %s" % (returncode, success_codes),
                    level=error_level
                )
                _fail = True
            if parser.num_errors:
                self.log("failures found while parsing output", level=error_level)
                _fail = True
            if _fail:
                self.return_code = fatal_exit_code
                self.fatal("Halting on failure while running %s" % command,
                           exit_code=fatal_exit_code)
        if return_type == 'num_errors':
            return parser.num_errors
        return returncode

    def get_output_from_command(self, command, cwd=None,
                                halt_on_failure=False, env=None,
                                silent=False, log_level=INFO,
                                tmpfile_base_path='tmpfile',
                                return_type='output', save_tmpfiles=False,
                                throw_exception=False, fatal_exit_code=2,
                                ignore_errors=False, success_codes=None):
        """Similar to run_command, but where run_command is an
        os.system(command) analog, get_output_from_command is a `command`
        analog.

        Less error checking by design, though if we figure out how to
        do it without borking the output, great.

        TODO: binary mode? silent is kinda like that.
        TODO: since p.wait() can take a long time, optionally log something
        every N seconds?
        TODO: optionally only keep the first or last (N) line(s) of output?
        TODO: optionally only return the tmp_stdout_filename?

        ignore_errors=True is for the case where a command might produce standard
        error output, but you don't particularly care; setting to True will
        cause standard error to be logged at DEBUG rather than ERROR

        Args:
            command (str | list): command or list of commands to
              execute and log.
            cwd (str, optional): directory path from where to execute the
              command. Defaults to `None`.
            halt_on_failure (bool, optional): whether or not to redefine the
              log level as `FATAL` on error. Defaults to False.
            env (dict, optional): key-value of environment values to use to
              run the command. Defaults to None.
            silent (bool, optional): whether or not to output the stdout of
              executing the command. Defaults to False.
            log_level (str, optional): log level name to use on normal execution.
              Defaults to `INFO`.
            tmpfile_base_path (str, optional): base path of the file to which
              the output will be writen to. Defaults to 'tmpfile'.
            return_type (str, optional): if equal to 'output' then the complete
              output of the executed command is returned, otherwise the written
              filenames are returned. Defaults to 'output'.
            save_tmpfiles (bool, optional): whether or not to save the temporary
              files created from the command output. Defaults to False.
            throw_exception (bool, optional): whether or not to raise an
              exception if the return value of the command is not zero.
              Defaults to False.
            fatal_exit_code (int, optional): call self.fatal if the return value
              of the command match this value.
            ignore_errors (bool, optional): whether or not to change the log
              level to `ERROR` for the output of stderr. Defaults to False.
            success_codes (int, optional): numeric value to compare against
              the command return value.

        Returns:
            None: if the cwd is not a directory.
            None: on IOError.
            tuple: stdout and stderr filenames.
            str: stdout output.
        """
        if cwd:
            if not os.path.isdir(cwd):
                level = ERROR
                if halt_on_failure:
                    level = FATAL
                self.log("Can't run command %s in non-existent directory %s!" %
                         (command, cwd), level=level)
                return None
            self.info("Getting output from command: %s in %s" % (command, cwd))
        else:
            self.info("Getting output from command: %s" % command)
        if isinstance(command, list):
            self.info("Copy/paste: %s" % subprocess.list2cmdline(command))
        # This could potentially return something?
        tmp_stdout = None
        tmp_stderr = None
        tmp_stdout_filename = '%s_stdout' % tmpfile_base_path
        tmp_stderr_filename = '%s_stderr' % tmpfile_base_path
        if success_codes is None:
            success_codes = [0]

        # TODO probably some more elegant solution than 2 similar passes
        try:
            tmp_stdout = open(tmp_stdout_filename, 'w')
        except IOError:
            level = ERROR
            if halt_on_failure:
                level = FATAL
            self.log("Can't open %s for writing!" % tmp_stdout_filename +
                     self.exception(), level=level)
            return None
        try:
            tmp_stderr = open(tmp_stderr_filename, 'w')
        except IOError:
            level = ERROR
            if halt_on_failure:
                level = FATAL
            self.log("Can't open %s for writing!" % tmp_stderr_filename +
                     self.exception(), level=level)
            return None
        shell = True
        if isinstance(command, list):
            shell = False
        p = subprocess.Popen(command, shell=shell, stdout=tmp_stdout,
                             cwd=cwd, stderr=tmp_stderr, env=env)
        # XXX: changed from self.debug to self.log due to this error:
        #      TypeError: debug() takes exactly 1 argument (2 given)
        self.log("Temporary files: %s and %s" % (tmp_stdout_filename, tmp_stderr_filename), level=DEBUG)
        p.wait()
        tmp_stdout.close()
        tmp_stderr.close()
        return_level = DEBUG
        output = None
        if return_type == 'output' or not silent:
            if os.path.exists(tmp_stdout_filename) and os.path.getsize(tmp_stdout_filename):
                output = self.read_from_file(tmp_stdout_filename,
                                             verbose=False)
                if not silent:
                    self.log("Output received:", level=log_level)
                    output_lines = output.rstrip().splitlines()
                    for line in output_lines:
                        if not line or line.isspace():
                            continue
                        line = line.decode("utf-8")
                        self.log(' %s' % line, level=log_level)
                    output = '\n'.join(output_lines)
        if os.path.exists(tmp_stderr_filename) and os.path.getsize(tmp_stderr_filename):
            if not ignore_errors:
                return_level = ERROR
            self.log("Errors received:", level=return_level)
            errors = self.read_from_file(tmp_stderr_filename,
                                         verbose=False)
            for line in errors.rstrip().splitlines():
                if not line or line.isspace():
                    continue
                line = line.decode("utf-8")
                self.log(' %s' % line, level=return_level)
        elif p.returncode not in success_codes and not ignore_errors:
            return_level = ERROR
        # Clean up.
        if not save_tmpfiles:
            self.rmtree(tmp_stderr_filename, log_level=DEBUG)
            self.rmtree(tmp_stdout_filename, log_level=DEBUG)
        if p.returncode and throw_exception:
            raise subprocess.CalledProcessError(p.returncode, command)
        self.log("Return code: %d" % p.returncode, level=return_level)
        if halt_on_failure and return_level == ERROR:
            self.return_code = fatal_exit_code
            self.fatal("Halting on failure while running %s" % command,
                       exit_code=fatal_exit_code)
        # Hm, options on how to return this? I bet often we'll want
        # output_lines[0] with no newline.
        if return_type != 'output':
            return (tmp_stdout_filename, tmp_stderr_filename)
        else:
            return output

    def _touch_file(self, file_name, times=None, error_level=FATAL):
        """touch a file.

        Args:
            file_name (str): name of the file to touch.
            times (tuple, optional): 2-tuple as specified by `os.utime`_
              Defaults to None.
            error_level (str, optional): log level name in case of error.
              Defaults to `FATAL`.

        .. _`os.utime`:
           https://docs.python.org/3.4/library/os.html?highlight=os.utime#os.utime
        """
        self.info("Touching: %s" % file_name)
        try:
            os.utime(file_name, times)
        except OSError:
            try:
                open(file_name, 'w').close()
            except IOError as e:
                msg = "I/O error(%s): %s" % (e.errno, e.strerror)
                self.log(msg, error_level=error_level)
        os.utime(file_name, times)

    def unpack(self, filename, extract_to, extract_dirs=None,
               error_level=ERROR, fatal_exit_code=2, verbose=False):
        """The method allows to extract a file regardless of its extension.

        Args:
            filename (str): filename of the compressed file.
            extract_to (str): where to extract the compressed file.
            extract_dirs (list, optional): directories inside the archive file to extract.
                                           Defaults to `None`.
            fatal_exit_code (int, optional): call `self.fatal` if the return value
              of the command is not in `success_codes`. Defaults to 2.
            verbose (bool, optional): whether or not extracted content should be displayed.
                                      Defaults to False.

        Raises:
            IOError: on `filename` file not found.

        """
        if not os.path.isfile(filename):
            raise IOError('Could not find file to extract: %s' % filename)

        if zipfile.is_zipfile(filename):
            try:
                self.info('Using ZipFile to extract {} to {}'.format(filename, extract_to))
                with zipfile.ZipFile(filename) as bundle:
                    for entry in self._filter_entries(bundle.namelist(), extract_dirs):
                        if verbose:
                            self.info(' %s' % entry)
                        bundle.extract(entry, path=extract_to)

                        # ZipFile doesn't preserve permissions during extraction:
                        # http://bugs.python.org/issue15795
                        fname = os.path.realpath(os.path.join(extract_to, entry))
                        mode = bundle.getinfo(entry).external_attr >> 16 & 0x1FF
                        # Only set permissions if attributes are available. Otherwise all
                        # permissions will be removed eg. on Windows.
                        if mode:
                            os.chmod(fname, mode)
            except zipfile.BadZipfile as e:
                self.log('%s (%s)' % (e.message, filename),
                         level=error_level, exit_code=fatal_exit_code)

        # Bug 1211882 - is_tarfile cannot be trusted for dmg files
        elif tarfile.is_tarfile(filename) and not filename.lower().endswith('.dmg'):
            try:
                self.info('Using TarFile to extract {} to {}'.format(filename, extract_to))
                with tarfile.open(filename) as bundle:
                    for entry in self._filter_entries(bundle.getnames(), extract_dirs):
                        if verbose:
                            self.info(' %s' % entry)
                        bundle.extract(entry, path=extract_to)
            except tarfile.TarError as e:
                self.log('%s (%s)' % (e.message, filename),
                         level=error_level, exit_code=fatal_exit_code)
        else:
            self.log('No extraction method found for: %s' % filename,
                     level=error_level, exit_code=fatal_exit_code)

    def is_taskcluster(self):
        """Returns boolean indicating if we're running in TaskCluster."""
        # This may need expanding in the future to work on
        return 'TASKCLUSTER_WORKER_TYPE' in os.environ


# LogMixin {{{1
class LogMixin(object):
    """This is a mixin for any object to access similar logging functionality

    The logging functionality described here is specially useful for those
    objects with self.config and self.log_obj member variables
    """

    def _log_level_at_least(self, level):
        """ Check if the current logging level is greater or equal than level

        Args:
            level (str): log level name to compare against mozharness log levels
                         names

        Returns:
            bool: True if the current logging level is great or equal than level,
                  False otherwise
        """
        log_level = INFO
        levels = [DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL]
        if hasattr(self, 'config'):
            log_level = self.config.get('log_level', INFO)
        return levels.index(level) >= levels.index(log_level)

    def _print(self, message, stderr=False):
        """ prints a message to the sys.stdout or sys.stderr according to the
        value of the stderr argument.

        Args:
            message (str): The message to be printed
            stderr (bool, optional): if True, message will be printed to
                                     sys.stderr. Defaults to False.

        Returns:
            None
        """
        if not hasattr(self, 'config') or self.config.get('log_to_console', True):
            if stderr:
                print >> sys.stderr, message
            else:
                print message

    def log(self, message, level=INFO, exit_code=-1):
        """ log the message passed to it according to level, exit if level == FATAL

        Args:
            message (str): message to be logged
            level (str, optional): logging level of the message. Defaults to INFO
            exit_code (int, optional): exit code to log before the scripts calls
                                       SystemExit.

        Returns:
            None
        """
        if self.log_obj:
            return self.log_obj.log_message(
                message, level=level,
                exit_code=exit_code,
                post_fatal_callback=self._post_fatal,
            )
        if level == INFO:
            if self._log_level_at_least(level):
                self._print(message)
        elif level == DEBUG:
            if self._log_level_at_least(level):
                self._print('DEBUG: %s' % message)
        elif level in (WARNING, ERROR, CRITICAL):
            if self._log_level_at_least(level):
                self._print("%s: %s" % (level.upper(), message), stderr=True)
        elif level == FATAL:
            if self._log_level_at_least(level):
                self._print("FATAL: %s" % message, stderr=True)
            raise SystemExit(exit_code)

    def worst_level(self, target_level, existing_level, levels=None):
        """Compare target_level with existing_level according to levels values
        and return the worst among them.

        Args:
            target_level (str): minimum logging level to which the current object
                                should be set
            existing_level (str): current logging level
            levels (list(str), optional): list of logging levels names to compare
                                          target_level and existing_level against.
                                          Defaults to mozharness log level
                                          list sorted from most to less critical.

        Returns:
            str: the logging lavel that is closest to the first levels value,
                 i.e. levels[0]
        """
        if not levels:
            levels = [FATAL, CRITICAL, ERROR, WARNING, INFO, DEBUG, IGNORE]
        if target_level not in levels:
            self.fatal("'%s' not in %s'." % (target_level, levels))
        for l in levels:
            if l in (target_level, existing_level):
                return l

    # Copying Bear's dumpException():
    # https://hg.mozilla.org/build/tools/annotate/1485f23c38e0/sut_tools/sut_lib.py#l23
    def exception(self, message=None, level=ERROR):
        """ log an exception message base on the log level passed to it.

        This function fetches the information of the current exception being handled and
        adds it to the message argument.

        Args:
            message (str, optional): message to be printed at the beginning of the log.
                                     Default to an empty string.
            level (str, optional): log level to use for the logging. Defaults to ERROR

        Returns:
            None
        """
        tb_type, tb_value, tb_traceback = sys.exc_info()
        if message is None:
            message = ""
        else:
            message = "%s\n" % message
        for s in traceback.format_exception(tb_type, tb_value, tb_traceback):
            message += "%s\n" % s
        # Log at the end, as a fatal will attempt to exit after the 1st line.
        self.log(message, level=level)

    def debug(self, message):
        """ calls the log method with DEBUG as logging level

        Args:
            message (str): message to log
        """
        self.log(message, level=DEBUG)

    def info(self, message):
        """ calls the log method with INFO as logging level

        Args:
            message (str): message to log
        """
        self.log(message, level=INFO)

    def warning(self, message):
        """ calls the log method with WARNING as logging level

        Args:
            message (str): message to log
        """
        self.log(message, level=WARNING)

    def error(self, message):
        """ calls the log method with ERROR as logging level

        Args:
            message (str): message to log
        """
        self.log(message, level=ERROR)

    def critical(self, message):
        """ calls the log method with CRITICAL as logging level

        Args:
            message (str): message to log
        """
        self.log(message, level=CRITICAL)

    def fatal(self, message, exit_code=-1):
        """ calls the log method with FATAL as logging level

        Args:
            message (str): message to log
            exit_code (int, optional): exit code to use for the SystemExit
                                       exception to be raised. Default to -1.
        """
        self.log(message, level=FATAL, exit_code=exit_code)

    def _post_fatal(self, message=None, exit_code=None):
        """ Sometimes you want to create a report or cleanup
        or notify on fatal(); override this method to do so.

        Please don't use this for anything significantly long-running.

        Args:
            message (str, optional): message to report. Default to None
            exit_code (int, optional): exit code to use for the SystemExit
                                       exception to be raised. Default to None
        """
        pass


# BaseScript {{{1
class BaseScript(ScriptMixin, LogMixin, object):
    def __init__(self, config_options=None, ConfigClass=BaseConfig,
                 default_log_level="info", **kwargs):
        self._return_code = 0
        super(BaseScript, self).__init__()

        # Collect decorated methods. We simply iterate over the attributes of
        # the current class instance and look for signatures deposited by
        # the decorators.
        self._listeners = dict(
            pre_run=[],
            pre_action=[],
            post_action=[],
            post_run=[],
        )
        for k in dir(self):
            item = getattr(self, k)

            # We only decorate methods, so ignore other types.
            if not inspect.ismethod(item):
                continue

            if hasattr(item, '_pre_run_listener'):
                self._listeners['pre_run'].append(k)

            if hasattr(item, '_pre_action_listener'):
                self._listeners['pre_action'].append((
                    k,
                    item._pre_action_listener))

            if hasattr(item, '_post_action_listener'):
                self._listeners['post_action'].append((
                    k,
                    item._post_action_listener))

            if hasattr(item, '_post_run_listener'):
                self._listeners['post_run'].append(k)

        self.log_obj = None
        self.abs_dirs = None
        if config_options is None:
            config_options = []
        self.summary_list = []
        self.failures = []
        rw_config = ConfigClass(config_options=config_options, **kwargs)
        self.config = rw_config.get_read_only_config()
        self.actions = tuple(rw_config.actions)
        self.all_actions = tuple(rw_config.all_actions)
        self.env = None
        self.new_log_obj(default_log_level=default_log_level)
        self.script_obj = self

        # Indicate we're a source checkout if VCS directory is present at the
        # appropriate place. This code will break if this file is ever moved
        # to another directory.
        self.topsrcdir = None

        srcreldir = 'testing/mozharness/mozharness/base'
        here = os.path.normpath(os.path.dirname(__file__))
        if here.replace('\\', '/').endswith(srcreldir):
            topsrcdir = os.path.normpath(os.path.join(here, '..', '..',
                                                      '..', '..'))
            hg_dir = os.path.join(topsrcdir, '.hg')
            git_dir = os.path.join(topsrcdir, '.git')
            if os.path.isdir(hg_dir) or os.path.isdir(git_dir):
                self.topsrcdir = topsrcdir

        # Set self.config to read-only.
        #
        # We can create intermediate config info programmatically from
        # this in a repeatable way, with logs; this is how we straddle the
        # ideal-but-not-user-friendly static config and the
        # easy-to-write-hard-to-debug writable config.
        #
        # To allow for other, script-specific configurations
        # (e.g., buildbot props json parsing), before locking,
        # call self._pre_config_lock().  If needed, this method can
        # alter self.config.
        self._pre_config_lock(rw_config)
        self._config_lock()

        self.info("Run as %s" % rw_config.command_line)
        if self.config.get("dump_config_hierarchy"):
            # we only wish to dump and display what self.config is made up of,
            # against the current script + args, without actually running any
            # actions
            self._dump_config_hierarchy(rw_config.all_cfg_files_and_dicts)
        if self.config.get("dump_config"):
            self.dump_config(exit_on_finish=True)

    def _dump_config_hierarchy(self, cfg_files):
        """ interpret each config file used.

        This will show which keys/values are being added or overwritten by
        other config files depending on their hierarchy (when they were added).
        """
        # go through each config_file. We will start with the lowest and
        # print its keys/values that are being used in self.config. If any
        # keys/values are present in a config file with a higher precedence,
        # ignore those.
        dirs = self.query_abs_dirs()
        cfg_files_dump_config = {}  # we will dump this to file
        # keep track of keys that did not come from a config file
        keys_not_from_file = set(self.config.keys())
        if not cfg_files:
            cfg_files = []
        self.info("Total config files: %d" % (len(cfg_files)))
        if len(cfg_files):
            self.info("cfg files used from lowest precedence to highest:")
        for i, (target_file, target_dict) in enumerate(cfg_files):
            unique_keys = set(target_dict.keys())
            unique_dict = {}
            # iterate through the target_dicts remaining 'higher' cfg_files
            remaining_cfgs = cfg_files[slice(i + 1, len(cfg_files))]
            # where higher == more precedent
            for ii, (higher_file, higher_dict) in enumerate(remaining_cfgs):
                # now only keep keys/values that are not overwritten by a
                # higher config
                unique_keys = unique_keys.difference(set(higher_dict.keys()))
            # unique_dict we know now has only keys/values that are unique to
            # this config file.
            unique_dict = dict(
                (key, target_dict.get(key)) for key in unique_keys
            )
            cfg_files_dump_config[target_file] = unique_dict
            self.action_message("Config File %d: %s" % (i + 1, target_file))
            self.info(pprint.pformat(unique_dict))
            # let's also find out which keys/values from self.config are not
            # from each target config file dict
            keys_not_from_file = keys_not_from_file.difference(
                set(target_dict.keys())
            )
        not_from_file_dict = dict(
            (key, self.config.get(key)) for key in keys_not_from_file
        )
        cfg_files_dump_config["not_from_cfg_file"] = not_from_file_dict
        self.action_message("Not from any config file (default_config, "
                            "cmd line options, etc)")
        self.info(pprint.pformat(not_from_file_dict))

        # finally, let's dump this output as JSON and exit early
        self.dump_config(
            os.path.join(dirs['abs_log_dir'], "localconfigfiles.json"),
            cfg_files_dump_config, console_output=False, exit_on_finish=True
        )

    def _pre_config_lock(self, rw_config):
        """This empty method can allow for config checking and manipulation
        before the config lock, when overridden in scripts.
        """
        pass

    def _config_lock(self):
        """After this point, the config is locked and should not be
        manipulated (based on mozharness.base.config.ReadOnlyDict)
        """
        self.config.lock()

    def _possibly_run_method(self, method_name, error_if_missing=False):
        """This is here for run().
        """
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            return getattr(self, method_name)()
        elif error_if_missing:
            self.error("No such method %s!" % method_name)

    @PostScriptRun
    def copy_logs_to_upload_dir(self):
        """Copies logs to the upload directory"""
        self.info("Copying logs to upload dir...")
        log_files = ['localconfig.json']
        for log_name in self.log_obj.log_files.keys():
            log_files.append(self.log_obj.log_files[log_name])
        dirs = self.query_abs_dirs()
        for log_file in log_files:
            self.copy_to_upload_dir(os.path.join(dirs['abs_log_dir'], log_file),
                                    dest=os.path.join('logs', log_file),
                                    short_desc='%s log' % log_name,
                                    long_desc='%s log' % log_name,
                                    max_backups=self.config.get("log_max_rotate", 0))

    def run_action(self, action):
        if action not in self.actions:
            self.action_message("Skipping %s step." % action)
            return

        method_name = action.replace("-", "_")
        self.action_message("Running %s step." % action)

        # An exception during a pre action listener should abort execution.
        for fn, target in self._listeners['pre_action']:
            if target is not None and target != action:
                continue

            try:
                self.info("Running pre-action listener: %s" % fn)
                method = getattr(self, fn)
                method(action)
            except Exception:
                self.error("Exception during pre-action for %s: %s" % (
                    action, traceback.format_exc()))

                for fn, target in self._listeners['post_action']:
                    if target is not None and target != action:
                        continue

                    try:
                        self.info("Running post-action listener: %s" % fn)
                        method = getattr(self, fn)
                        method(action, success=False)
                    except Exception:
                        self.error("An additional exception occurred during "
                                   "post-action for %s: %s" % (action,
                                   traceback.format_exc()))

                self.fatal("Aborting due to exception in pre-action listener.")

        # We always run post action listeners, even if the main routine failed.
        success = False
        try:
            self.info("Running main action method: %s" % method_name)
            self._possibly_run_method("preflight_%s" % method_name)
            self._possibly_run_method(method_name, error_if_missing=True)
            self._possibly_run_method("postflight_%s" % method_name)
            success = True
        finally:
            post_success = True
            for fn, target in self._listeners['post_action']:
                if target is not None and target != action:
                    continue

                try:
                    self.info("Running post-action listener: %s" % fn)
                    method = getattr(self, fn)
                    method(action, success=success and self.return_code == 0)
                except Exception:
                    post_success = False
                    self.error("Exception during post-action for %s: %s" % (
                        action, traceback.format_exc()))

            step_result = 'success' if success else 'failed'
            self.action_message("Finished %s step (%s)" % (action, step_result))

            if not post_success:
                self.fatal("Aborting due to failure in post-action listener.")

    def run(self):
        """Default run method.
        This is the "do everything" method, based on actions and all_actions.

        First run self.dump_config() if it exists.
        Second, go through the list of all_actions.
        If they're in the list of self.actions, try to run
        self.preflight_ACTION(), self.ACTION(), and self.postflight_ACTION().

        Preflight is sanity checking before doing anything time consuming or
        destructive.

        Postflight is quick testing for success after an action.

        """
        for fn in self._listeners['pre_run']:
            try:
                self.info("Running pre-run listener: %s" % fn)
                method = getattr(self, fn)
                method()
            except Exception:
                self.error("Exception during pre-run listener: %s" %
                           traceback.format_exc())

                for fn in self._listeners['post_run']:
                    try:
                        method = getattr(self, fn)
                        method()
                    except Exception:
                        self.error("An additional exception occurred during a "
                                   "post-run listener: %s" % traceback.format_exc())

                self.fatal("Aborting due to failure in pre-run listener.")

        self.dump_config()
        try:
            for action in self.all_actions:
                self.run_action(action)
        except Exception:
            self.fatal("Uncaught exception: %s" % traceback.format_exc())
        finally:
            post_success = True
            for fn in self._listeners['post_run']:
                try:
                    self.info("Running post-run listener: %s" % fn)
                    method = getattr(self, fn)
                    method()
                except Exception:
                    post_success = False
                    self.error("Exception during post-run listener: %s" %
                               traceback.format_exc())

            if not post_success:
                self.fatal("Aborting due to failure in post-run listener.")
        if self.config.get("copy_logs_post_run", True):
            self.copy_logs_to_upload_dir()

        return self.return_code

    def run_and_exit(self):
        """Runs the script and exits the current interpreter."""
        rc = self.run()
        if rc != 0:
            self.warning("returning nonzero exit status %d" % rc)
        sys.exit(rc)

    def clobber(self):
        """
        Delete the working directory
        """
        dirs = self.query_abs_dirs()
        self.rmtree(dirs['abs_work_dir'], error_level=FATAL)

    def query_abs_dirs(self):
        """We want to be able to determine where all the important things
        are.  Absolute paths lend themselves well to this, though I wouldn't
        be surprised if this causes some issues somewhere.

        This should be overridden in any script that has additional dirs
        to query.

        The query_* methods tend to set self.VAR variables as their
        runtime cache.
        """
        if self.abs_dirs:
            return self.abs_dirs
        c = self.config
        dirs = {}
        dirs['base_work_dir'] = c['base_work_dir']
        dirs['abs_work_dir'] = os.path.join(c['base_work_dir'], c['work_dir'])
        dirs['abs_upload_dir'] = os.path.join(dirs['abs_work_dir'], 'upload')
        dirs['abs_log_dir'] = os.path.join(c['base_work_dir'], c.get('log_dir', 'logs'))
        self.abs_dirs = dirs
        return self.abs_dirs

    def dump_config(self, file_path=None, config=None,
                    console_output=True, exit_on_finish=False):
        """Dump self.config to localconfig.json
        """
        config = config or self.config
        dirs = self.query_abs_dirs()
        if not file_path:
            file_path = os.path.join(dirs['abs_log_dir'], "localconfig.json")
        self.info("Dumping config to %s." % file_path)
        self.mkdir_p(os.path.dirname(file_path))
        json_config = json.dumps(config, sort_keys=True, indent=4)
        fh = codecs.open(file_path, encoding='utf-8', mode='w+')
        fh.write(json_config)
        fh.close()
        if console_output:
            self.info(pprint.pformat(config))
        if exit_on_finish:
            sys.exit()

    # logging {{{2
    def new_log_obj(self, default_log_level="info"):
        c = self.config
        log_dir = os.path.join(c['base_work_dir'], c.get('log_dir', 'logs'))
        log_config = {
            "logger_name": 'Simple',
            "log_name": 'log',
            "log_dir": log_dir,
            "log_level": default_log_level,
            "log_format": '%(asctime)s %(levelname)8s - %(message)s',
            "log_to_console": True,
            "append_to_log": False,
        }
        log_type = self.config.get("log_type", "multi")
        for key in log_config.keys():
            value = self.config.get(key, None)
            if value is not None:
                log_config[key] = value
        if log_type == "multi":
            self.log_obj = MultiFileLogger(**log_config)
        else:
            self.log_obj = SimpleFileLogger(**log_config)

    def action_message(self, message):
        self.info("[mozharness: %sZ] %s" % (
            datetime.utcnow().isoformat(' '), message))

    def summary(self):
        """Print out all the summary lines added via add_summary()
        throughout the script.

        I'd like to revisit how to do this in a prettier fashion.
        """
        self.action_message("%s summary:" % self.__class__.__name__)
        if self.summary_list:
            for item in self.summary_list:
                try:
                    self.log(item['message'], level=item['level'])
                except ValueError:
                    """log is closed; print as a default. Ran into this
                    when calling from __del__()"""
                    print "### Log is closed! (%s)" % item['message']

    def add_summary(self, message, level=INFO):
        self.summary_list.append({'message': message, 'level': level})
        # TODO write to a summary-only log?
        # Summaries need a lot more love.
        self.log(message, level=level)

    def add_failure(self, key, message="%(key)s failed.", level=ERROR,
                    increment_return_code=True):
        if key not in self.failures:
            self.failures.append(key)
            self.add_summary(message % {'key': key}, level=level)
            if increment_return_code:
                self.return_code += 1

    def query_failure(self, key):
        return key in self.failures

    def summarize_success_count(self, success_count, total_count,
                                message="%d of %d successful.",
                                level=None):
        if level is None:
            level = INFO
            if success_count < total_count:
                level = ERROR
        self.add_summary(message % (success_count, total_count),
                         level=level)

    def copy_to_upload_dir(self, target, dest=None, short_desc="unknown",
                           long_desc="unknown", log_level=DEBUG,
                           error_level=ERROR, max_backups=None,
                           compress=False, upload_dir=None):
        """Copy target file to upload_dir/dest.

        Potentially update a manifest in the future if we go that route.

        Currently only copies a single file; would be nice to allow for
        recursive copying; that would probably done by creating a helper
        _copy_file_to_upload_dir().

        short_desc and long_desc are placeholders for if/when we add
        upload_dir manifests.
        """
        dest_filename_given = dest is not None
        if upload_dir is None:
            upload_dir = self.query_abs_dirs()['abs_upload_dir']
        if dest is None:
            dest = os.path.basename(target)
        if dest.endswith('/'):
            dest_file = os.path.basename(target)
            dest_dir = os.path.join(upload_dir, dest)
            dest_filename_given = False
        else:
            dest_file = os.path.basename(dest)
            dest_dir = os.path.join(upload_dir, os.path.dirname(dest))
        if compress and not dest_filename_given:
            dest_file += ".gz"
        dest = os.path.join(dest_dir, dest_file)
        if not os.path.exists(target):
            self.log("%s doesn't exist!" % target, level=error_level)
            return None
        self.mkdir_p(dest_dir)
        if os.path.exists(dest):
            if os.path.isdir(dest):
                self.log("%s exists and is a directory!" % dest, level=error_level)
                return -1
            if max_backups:
                # Probably a better way to do this
                oldest_backup = 0
                backup_regex = re.compile("^%s\.(\d+)$" % dest_file)
                for filename in os.listdir(dest_dir):
                    r = backup_regex.match(filename)
                    if r and int(r.groups()[0]) > oldest_backup:
                        oldest_backup = int(r.groups()[0])
                for backup_num in range(oldest_backup, 0, -1):
                    # TODO more error checking?
                    if backup_num >= max_backups:
                        self.rmtree(os.path.join(dest_dir, "%s.%d" % (dest_file, backup_num)),
                                    log_level=log_level)
                    else:
                        self.move(os.path.join(dest_dir, "%s.%d" % (dest_file, backup_num)),
                                  os.path.join(dest_dir, "%s.%d" % (dest_file, backup_num + 1)),
                                  log_level=log_level)
                if self.move(dest, "%s.1" % dest, log_level=log_level):
                    self.log("Unable to move %s!" % dest, level=error_level)
                    return -1
            else:
                if self.rmtree(dest, log_level=log_level):
                    self.log("Unable to remove %s!" % dest, level=error_level)
                    return -1
        self.copyfile(target, dest, log_level=log_level, compress=compress)
        if os.path.exists(dest):
            return dest
        else:
            self.log("%s doesn't exist after copy!" % dest, level=error_level)
            return None

    def get_hash_for_file(self, file_path, hash_type="sha512"):
        bs = 65536
        hasher = hashlib.new(hash_type)
        with open(file_path, 'rb') as fh:
            buf = fh.read(bs)
            while len(buf) > 0:
                hasher.update(buf)
                buf = fh.read(bs)
        return hasher.hexdigest()

    @property
    def return_code(self):
        return self._return_code

    @return_code.setter
    def return_code(self, code):
        old_return_code, self._return_code = self._return_code, code
        if old_return_code != code:
            self.warning("setting return code to %d" % code)


# Virtualenv {{{1
virtualenv_config_options = [
    [["--virtualenv-path"], {
        "action": "store",
        "dest": "virtualenv_path",
        "default": "venv",
        "help": "Specify the path to the virtualenv top level directory"
    }],
    [["--virtualenv"], {
        "action": "store",
        "dest": "virtualenv",
        "help": "Specify the virtualenv executable to use"
    }],
    [["--find-links"], {
        "action": "extend",
        "dest": "find_links",
        "help": "URL to look for packages at"
    }],
    [["--pip-index"], {
        "action": "store_true",
        "default": True,
        "dest": "pip_index",
        "help": "Use pip indexes (default)"
    }],
    [["--no-pip-index"], {
        "action": "store_false",
        "dest": "pip_index",
        "help": "Don't use pip indexes"
    }],
]

class VirtualenvMixin(object):
    '''BaseScript mixin, designed to create and use virtualenvs.

    Config items:
     * virtualenv_path points to the virtualenv location on disk.
     * virtualenv_modules lists the module names.
     * MODULE_url list points to the module URLs (optional)
    Requires virtualenv to be in PATH.
    Depends on ScriptMixin
    '''
    python_paths = {}
    site_packages_path = None

    def __init__(self, *args, **kwargs):
        self._virtualenv_modules = []
        super(VirtualenvMixin, self).__init__(*args, **kwargs)

    def register_virtualenv_module(self, name=None, url=None, method=None,
                                   requirements=None, optional=False,
                                   two_pass=False, editable=False):
        """Register a module to be installed with the virtualenv.

        This method can be called up until create_virtualenv() to register
        modules that should be installed in the virtualenv.

        See the documentation for install_module for how the arguments are
        applied.
        """
        self._virtualenv_modules.append((name, url, method, requirements,
                                         optional, two_pass, editable))

    def query_virtualenv_path(self):
        """Determine the absolute path to the virtualenv."""
        dirs = self.query_abs_dirs()

        if 'abs_virtualenv_dir' in dirs:
            return dirs['abs_virtualenv_dir']

        p = self.config['virtualenv_path']
        if not p:
            self.fatal('virtualenv_path config option not set; '
                       'this should never happen')

        if os.path.isabs(p):
            return p
        else:
            return os.path.join(dirs['abs_work_dir'], p)

    def query_python_path(self, binary="python"):
        """Return the path of a binary inside the virtualenv, if
        c['virtualenv_path'] is set; otherwise return the binary name.
        Otherwise return None
        """
        if binary not in self.python_paths:
            bin_dir = 'bin'
            if self._is_windows():
                bin_dir = 'Scripts'
            virtualenv_path = self.query_virtualenv_path()
            self.python_paths[binary] = os.path.abspath(os.path.join(virtualenv_path, bin_dir, binary))

        return self.python_paths[binary]

    def query_python_site_packages_path(self):
        if self.site_packages_path:
            return self.site_packages_path
        python = self.query_python_path()
        self.site_packages_path = self.get_output_from_command(
            [python, '-c',
             'from distutils.sysconfig import get_python_lib; ' +
             'print(get_python_lib())'])
        return self.site_packages_path

    def package_versions(self, pip_freeze_output=None, error_level=WARNING, log_output=False):
        """
        reads packages from `pip freeze` output and returns a dict of
        {package_name: 'version'}
        """
        packages = {}

        if pip_freeze_output is None:
            # get the output from `pip freeze`
            pip = self.query_python_path("pip")
            if not pip:
                self.log("package_versions: Program pip not in path", level=error_level)
                return {}
            pip_freeze_output = self.get_output_from_command([pip, "freeze"], silent=True, ignore_errors=True)
            if not isinstance(pip_freeze_output, basestring):
                self.fatal("package_versions: Error encountered running `pip freeze`: %s" % pip_freeze_output)

        for line in pip_freeze_output.splitlines():
            # parse the output into package, version
            line = line.strip()
            if not line:
                # whitespace
                continue
            if line.startswith('-'):
                # not a package, probably like '-e http://example.com/path#egg=package-dev'
                continue
            if '==' not in line:
                self.fatal("pip_freeze_packages: Unrecognized output line: %s" % line)
            package, version = line.split('==', 1)
            packages[package] = version

        if log_output:
            self.info("Current package versions:")
            for package in sorted(packages):
                self.info("  %s == %s" % (package, packages[package]))

        return packages

    def is_python_package_installed(self, package_name, error_level=WARNING):
        """
        Return whether the package is installed
        """
        packages = self.package_versions(error_level=error_level).keys()
        return package_name.lower() in [package.lower() for package in packages]

    def install_module(self, module=None, module_url=None, install_method=None,
                       requirements=(), optional=False, global_options=[],
                       no_deps=False, editable=False):
        """
        Install module via pip.

        module_url can be a url to a python package tarball, a path to
        a directory containing a setup.py (absolute or relative to work_dir)
        or None, in which case it will default to the module name.

        requirements is a list of pip requirements files.  If specified, these
        will be combined with the module_url (if any), like so:

        pip install -r requirements1.txt -r requirements2.txt module_url
        """
        c = self.config
        dirs = self.query_abs_dirs()
        env = self.query_env()
        venv_path = self.query_virtualenv_path()
        self.info("Installing %s into virtualenv %s" % (module, venv_path))
        if not module_url:
            module_url = module
        if install_method in (None, 'pip'):
            if not module_url and not requirements:
                self.fatal("Must specify module and/or requirements")
            pip = self.query_python_path("pip")
            if c.get("verbose_pip"):
                command = [pip, "-v", "install"]
            else:
                command = [pip, "install"]
            if no_deps:
                command += ["--no-deps"]
            # To avoid timeouts with our pypi server, increase default timeout:
            # https://bugzilla.mozilla.org/show_bug.cgi?id=1007230#c802
            command += ['--timeout', str(c.get('pip_timeout', 120))]
            for requirement in requirements:
                command += ["-r", requirement]
            if c.get('find_links') and not c["pip_index"]:
                command += ['--no-index']
            for opt in global_options:
                command += ["--global-option", opt]
        elif install_method == 'easy_install':
            if not module:
                self.fatal("module parameter required with install_method='easy_install'")
            if requirements:
                # Install pip requirements files separately, since they're
                # not understood by easy_install.
                self.install_module(requirements=requirements,
                                    install_method='pip')
            # Allow easy_install to be overridden by
            # self.config['exes']['easy_install']
            default = 'easy_install'
            if self._is_windows():
                # Don't invoke `easy_install` directly on windows since
                # the 'install' in the executable name hits UAC
                # - http://answers.microsoft.com/en-us/windows/forum/windows_7-security/uac-message-do-you-want-to-allow-the-following/bea30ad8-9ef8-4897-aab4-841a65f7af71
                # - https://bugzilla.mozilla.org/show_bug.cgi?id=791840
                default = [self.query_python_path(), self.query_python_path('easy_install-script.py')]
            command = self.query_exe('easy_install', default=default, return_type="list")
        else:
            self.fatal("install_module() doesn't understand an install_method of %s!" % install_method)

        # Add --find-links pages to look at. Add --trusted-host automatically if
        # the host isn't secure. This allows modern versions of pip to connect
        # without requiring an override.
        proxxy = Proxxy(self.config, self.log_obj)
        trusted_hosts = set()
        for link in proxxy.get_proxies_and_urls(c.get('find_links', [])):
            parsed = urlparse.urlparse(link)

            try:
                socket.gethostbyname(parsed.hostname)
            except socket.gaierror as e:
                self.info('error resolving %s (ignoring): %s' %
                          (parsed.hostname, e.message))
                continue

            command.extend(["--find-links", link])
            if parsed.scheme != 'https':
                trusted_hosts.add(parsed.hostname)

        if (install_method != 'easy_install' and
                    self.pip_version >= distutils.version.LooseVersion('6.0')):
            for host in sorted(trusted_hosts):
                command.extend(['--trusted-host', host])

        # module_url can be None if only specifying requirements files
        if module_url:
            if editable:
                if install_method in (None, 'pip'):
                    command += ['-e']
                else:
                    self.fatal("editable installs not supported for install_method %s" % install_method)
            command += [module_url]

        # If we're only installing a single requirements file, use
        # the file's directory as cwd, so relative paths work correctly.
        cwd = dirs['abs_work_dir']
        if not module and len(requirements) == 1:
            cwd = os.path.dirname(requirements[0])

        quoted_command = subprocess.list2cmdline(command)
        # Allow for errors while building modules, but require a
        # return status of 0.
        self.retry(
            self.run_command,
            # None will cause default value to be used
            attempts=1 if optional else None,
            good_statuses=(0,),
            error_level=WARNING if optional else FATAL,
            error_message='Could not install python package: ' + quoted_command + ' failed after %(attempts)d tries!',
            args=[command, ],
            kwargs={
                'error_list': VirtualenvErrorList,
                'cwd': cwd,
                'env': env,
                # WARNING only since retry will raise final FATAL if all
                # retry attempts are unsuccessful - and we only want
                # an ERROR of FATAL if *no* retry attempt works
                'error_level': WARNING,
            }
        )

    def create_virtualenv(self, modules=(), requirements=()):
        """
        Create a python virtualenv.

        The virtualenv exe can be defined in c['virtualenv'] or
        c['exes']['virtualenv'], as a string (path) or list (path +
        arguments).

        c['virtualenv_python_dll'] is an optional config item that works
        around an old windows virtualenv bug.

        virtualenv_modules can be a list of module names to install, e.g.

            virtualenv_modules = ['module1', 'module2']

        or it can be a heterogeneous list of modules names and dicts that
        define a module by its name, url-or-path, and a list of its global
        options.

            virtualenv_modules = [
                {
                    'name': 'module1',
                    'url': None,
                    'global_options': ['--opt', '--without-gcc']
                },
                {
                    'name': 'module2',
                    'url': 'http://url/to/package',
                    'global_options': ['--use-clang']
                },
                {
                    'name': 'module3',
                    'url': os.path.join('path', 'to', 'setup_py', 'dir')
                    'global_options': []
                },
                'module4'
            ]

        virtualenv_requirements is an optional list of pip requirements files to
        use when invoking pip, e.g.,

            virtualenv_requirements = [
                '/path/to/requirements1.txt',
                '/path/to/requirements2.txt'
            ]
        """
        c = self.config
        dirs = self.query_abs_dirs()
        venv_path = self.query_virtualenv_path()
        self.info("Creating virtualenv %s" % venv_path)

        # If running from a source checkout, use the virtualenv that is
        # vendored since that is deterministic.
        if self.topsrcdir:
            virtualenv = [
                sys.executable,
                os.path.join(self.topsrcdir, 'python', 'virtualenv', 'virtualenv.py')
            ]
            virtualenv_options = c.get('virtualenv_options', [])
            # Don't create symlinks. If we don't do this, permissions issues may
            # hinder virtualenv creation or operation. Ideally we should do this
            # below when using the system virtualenv. However, this is a newer
            # feature and isn't guaranteed to be supported.
            virtualenv_options.append('--always-copy')

        # No source checkout. Try to find virtualenv from config options
        # or search path.
        else:
            virtualenv = c.get('virtualenv', self.query_exe('virtualenv'))
            if isinstance(virtualenv, str):
                # allow for [python, virtualenv] in config
                virtualenv = [virtualenv]

            if not os.path.exists(virtualenv[0]) and not self.which(virtualenv[0]):
                self.add_summary("The executable '%s' is not found; not creating "
                                 "virtualenv!" % virtualenv[0], level=FATAL)
                return -1

            # https://bugs.launchpad.net/virtualenv/+bug/352844/comments/3
            # https://bugzilla.mozilla.org/show_bug.cgi?id=700415#c50
            if c.get('virtualenv_python_dll'):
                # We may someday want to copy a differently-named dll, but
                # let's not think about that right now =\
                dll_name = os.path.basename(c['virtualenv_python_dll'])
                target = self.query_python_path(dll_name)
                scripts_dir = os.path.dirname(target)
                self.mkdir_p(scripts_dir)
                self.copyfile(c['virtualenv_python_dll'], target, error_level=WARNING)

            # make this list configurable?
            for module in ('distribute', 'pip'):
                if c.get('%s_url' % module):
                    self.download_file(c['%s_url' % module],
                                       parent_dir=dirs['abs_work_dir'])

            virtualenv_options = c.get('virtualenv_options',
                                       ['--no-site-packages', '--distribute'])

        if os.path.exists(self.query_python_path()):
            self.info("Virtualenv %s appears to already exist; skipping virtualenv creation." % self.query_python_path())
        else:
            self.mkdir_p(dirs['abs_work_dir'])
            self.run_command(virtualenv + virtualenv_options + [venv_path],
                             cwd=dirs['abs_work_dir'],
                             error_list=VirtualenvErrorList,
                             partial_env={'VIRTUALENV_NO_DOWNLOAD': "1"},
                             halt_on_failure=True)

        # Resolve the pip version so we can conditionally do things if we have
        # a modern pip.
        pip = self.query_python_path('pip')
        output = self.get_output_from_command([pip, '--version'],
                                              halt_on_failure=True)
        words = output.split()
        if words[0] != 'pip':
            self.fatal('pip --version output is weird: %s' % output)
        pip_version = words[1]
        self.pip_version = distutils.version.LooseVersion(pip_version)

        if not modules:
            modules = c.get('virtualenv_modules', [])
        if not requirements:
            requirements = c.get('virtualenv_requirements', [])
        if not modules and requirements:
            self.install_module(requirements=requirements,
                                install_method='pip')
        for module in modules:
            module_url = module
            global_options = []
            if isinstance(module, dict):
                if module.get('name', None):
                    module_name = module['name']
                else:
                    self.fatal("Can't install module without module name: %s" %
                               str(module))
                module_url = module.get('url', None)
                global_options = module.get('global_options', [])
            else:
                module_url = self.config.get('%s_url' % module, module_url)
                module_name = module
            install_method = 'pip'
            if module_name in ('pywin32',):
                install_method = 'easy_install'
            self.install_module(module=module_name,
                                module_url=module_url,
                                install_method=install_method,
                                requirements=requirements,
                                global_options=global_options)

        for module, url, method, requirements, optional, two_pass, editable in \
                self._virtualenv_modules:
            if two_pass:
                self.install_module(
                    module=module, module_url=url,
                    install_method=method, requirements=requirements or (),
                    optional=optional, no_deps=True, editable=editable
                )
            self.install_module(
                module=module, module_url=url,
                install_method=method, requirements=requirements or (),
                optional=optional, editable=editable
            )

        self.info("Done creating virtualenv %s." % venv_path)

        self.package_versions(log_output=True)

    def activate_virtualenv(self):
        """Import the virtualenv's packages into this Python interpreter."""
        bin_dir = os.path.dirname(self.query_python_path())
        activate = os.path.join(bin_dir, 'activate_this.py')
        execfile(activate, dict(__file__=activate))


class TransparencyCertIssuer(BaseScript, VirtualenvMixin):
    config_options = virtualenv_config_options

    # config_options = [
    #     [["--stage-product"], {
    #         "dest": "stage_product",
    #         "help": "Name of product used in file server's directory structure, eg: firefox, mobile",
    #     }],
    #     [["--version"], {
    #         "dest": "version",
    #         "help": "Version of release, eg: 39.0b5",
    #     }],
    #     [["--contact"], {
    #         "dest": "contact",
    #         "help": "Contact email to provide to Let's Encrypt"
    #     }],
    #     [["--summary"], {
    #         "dest": "summary",
    #         "help": "URL from which the SUMMARY file should be downloaded"
    #     }],
    #     [["--chain"], {
    #         "dest": "chain",
    #         "help": "File where the issued certificate chain should be written"
    #     }],
    # ]

    def __init__(self):
        BaseScript.__init__(self,
            config_options=self.config_options,
            config={
                "virtualenv_modules": [
                    "redo",
                    "requests",
                ],
                "virtualenv_path": "venv",
            },
            require_config_file=False,
            all_actions=["issue-cert"],
            default_actions=["issue-cert"],
        )

        self.product = self.config["stage_product"]
        self.version = self.config["version"]
        self.contact_email = self.config["contact"]
        self.summary_url = self.config["summary"]
        self.chain_filename = self.config["chain"]

    TRANSPARENCY_VERSION = "0"
    TRANSPARENCY_SUFFIX = "stage.fx-trans.net"

    def _make_transparency_name(self, tree_head_hex, version, product):
        version = re.sub("\.", "-", version)

        name = "{}.{}.{}.{}".format(version, product, self.TRANSPARENCY_VERSION, self.TRANSPARENCY_SUFFIX)

        while len(tree_head_hex) > 32:
            label = tree_head_hex[-32:]
            tree_head_hex = tree_head_hex[:-32]
            name = "{}.{}".format(label, name)

        if len(tree_head_hex) > 0:
            name = "{}.{}".format(tree_head_hex, name)

        return name


    def issue_cert(self):
        from subprocess import check_call
        from redo import retry
        import requests

        # Fetch summary file and parse out tree head
        def get_summary():
            r = requests.get(self.summary_url)
            r.raise_for_status()
            return r.text

        summary = retry(get_summary)
        tree_head = None
        for line in summary.split("\n"):
            tokens = re.split(r'\s+', line)
            if len(tokens) == 2 and tokens[1] == "TREE_HEAD":
                tree_head = tokens[0]

        if tree_head is None:
            raise Exception("No tree head found in summary file")

        base_name = "{}.{}".format("invalid", self.TRANSPARENCY_SUFFIX)
        trans_name = self._make_transparency_name(tree_head, self.version, self.product)

        # Read values from config.json
        here = os.path.dirname(os.path.abspath(__file__))
        config_json = os.path.join(here, '../config.json')

        with open(config_json) as config_file:
             config_vars = json.load(config_file)

        # Issue and save the certificate, then delete the extra files lego created
        lego_env = {
            "AWS_ACCESS_KEY_ID": config_vars["AWS_KEYS"]["AWS_ACCESS_KEY_ID"],
            "AWS_SECRET_ACCESS_KEY": config_vars["AWS_KEYS"]["AWS_SECRET_ACCESS_KEY"],
            "AWS_REGION": "us-west-2",
        }
        lego_command = " ".join([
            "/Users/btang/go/bin/lego",
            " --dns route53",
            " --domains {}".format(base_name),
            " --domains {}".format(trans_name),
            " --email {}".format(self.contact_email),
            " --accept-tos",
            "run"
        ])

        save_command = " ".join([
            "mv",
            "./.lego/certificates/{}.crt".format(base_name),
            self.chain_filename
        ])

        cleanup_command = "rm -rf ./.lego"

        check_call(lego_command, env=lego_env, shell=True)
        check_call(save_command, shell=True)
        check_call(cleanup_command, shell=True)


if __name__ == "__main__":
    myScript = TransparencyCertIssuer()
    myScript.run_and_exit()

# python binarytransparencyscript/issue-transparency-cert.py
