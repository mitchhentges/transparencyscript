import os
import requests
import requests_mock

from transparencyscript.utils import make_transparency_name, get_config_vars, get_password_vars, get_task_vars, \
    get_transparency_vars, get_lego_env, get_lego_command, get_save_command, get_chain, post_chain
from transparencyscript.test import get_fake_config, get_fake_passwords, get_fake_task, get_fake_transparency
from transparencyscript.constants import SUMMARY_TEXT, TRANSPARENCY_SUFFIX


def test_make_transparency_name():
    correct_name = "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0.stage." \
                   "fx-trans.net"

    tree_head_hex = "eae00f676fc07354cd509994f9946956462805e6950aacba4c1bc9028880efc2"
    version = "53.0b5"
    product = "firefox"

    assert make_transparency_name(tree_head_hex, version, product) == correct_name


def test_get_config_vars():
    fake_config_vars = get_fake_config()

    config_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_config.json')
    config_vars = get_config_vars(config_path)

    assert config_vars == fake_config_vars


def test_get_password_vars():
    fake_password_vars = get_fake_passwords()

    password_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_passwords.json')
    password_vars = get_password_vars(password_path)

    assert password_vars == fake_password_vars


def test_get_task_vars():
    fake_task_vars = get_fake_task()

    task_path = os.path.join(os.getcwd(), 'transparencyscript/test/fake_task.json')
    task_vars = get_task_vars(task_path)

    assert task_vars == fake_task_vars


def test_get_transparency_vars():
    fake_transparency_vars = get_fake_transparency()

    fake_config_vars = get_fake_config()
    fake_task_vars = get_fake_task()

    transparency_vars = get_transparency_vars(fake_config_vars, fake_task_vars)

    assert transparency_vars == fake_transparency_vars


def test_get_summary():
    correct_summary = SUMMARY_TEXT

    with requests_mock.Mocker() as m:
        m.get("https://ipv.sx/tmp/SHA256SUMMARY", text=correct_summary)
        summary = requests.get("https://ipv.sx/tmp/SHA256SUMMARY").text

    assert summary == correct_summary


def test_get_lego_env():
    correct_lego_env = {'AWS_ACCESS_KEY_ID': '*****', 'AWS_SECRET_ACCESS_KEY': '*****', 'AWS_REGION': 'us-west-2'}

    password_vars = get_fake_passwords()

    lego_env = get_lego_env(password_vars)

    assert lego_env == correct_lego_env


def test_get_lego_command():
    correct_lego_command = "/Users/btang/go/bin/lego  --dns route53  --domains invalid.stage.fx-trans.net  --domains " \
                           "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0." \
                           "stage.fx-trans.net  --email btang@mozilla.com  --path ./lego  " \
                           "--accept-tos run"

    config_vars = get_fake_config()
    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)
    trans_name = "eae00f676fc07354cd509994f9946956.462805e6950aacba4c1bc9028880efc2.53-0b5.firefox.0.stage.fx-trans.net"

    lego_command = get_lego_command(config_vars, base_name, trans_name)

    assert lego_command == correct_lego_command


def test_get_save_command():
    correct_save_command = "mv ./lego/certificates/invalid.stage.fx-trans.net.crt " \
                           "./transparencyscript/test/FAKE_TRANSPARENCY.pem"

    config_vars = get_fake_config()
    base_name = "{}.{}".format("invalid", TRANSPARENCY_SUFFIX)

    save_command = get_save_command(config_vars, base_name)

    assert save_command == correct_save_command


def test_get_chain():
    correct_req = '{"chain": ["MIIFgTCCBGmgAwIBAgISA2RjCEL7JTlwJbUFmX95dBdhMA0GCSqGSIb3DQEBCwUAMEoxCzAJBgNVBAYTAlVTM' \
                  'RYwFAYDVQQKEw1MZXQncyBFbmNyeXB0MSMwIQYDVQQDExpMZXQncyBFbmNyeXB0IEF1dGhvcml0eSBYMzAeFw0xNzA4MDgxNjE' \
                  '3MDBaFw0xNzExMDYxNjE3MDBaMCUxIzAhBgNVBAMTGmludmFsaWQuc3RhZ2UuZngtdHJhbnMubmV0MIIBIjANBgkqhkiG9w0BA' \
                  'QEFAAOCAQ8AMIIBCgKCAQEAtLKqMOVS3IPNVRMw+hzOTGyP+6VVyc4v3/w0Uaki1tTZX3o8u00+2iz8AxFA5Z/GvGsI5g3Djaw' \
                  'Iy7ZOpB3oA9qsuRt0Gf7PTVyiPycHi3Wp8hU5PYzjenIwzJ6eXYPPiqQCuAxgygNE6PAcU8xMbAy94tokLzk1Dg6yzRJSDuR7p' \
                  'wIWni6pMPK/xD6bamRxTsZx7A+I9NWYjG1B6+J1n0PQAovCGIY0m0hIvbCSmoTO63q8njJ+tHgwie7TFscVNca2qk0Q1+QXcLP' \
                  'lJKV723wJMMdzzB+JHBvqX4ShImQaVHsLPwZM77K3d8PIfpRPhHhiy8/UPUo5n3yXQDKkdQIDAQABo4IChDCCAoAwDgYDVR0PA' \
                  'QH/BAQDAgWgMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAAMB0GA1UdDgQWBBTSXXM+GndFLIt' \
                  'squNZ1if5QuKGrzAfBgNVHSMEGDAWgBSoSmpjBH3duubRObemRWXv86jsoTBvBggrBgEFBQcBAQRjMGEwLgYIKwYBBQUHMAGGI' \
                  'mh0dHA6Ly9vY3NwLmludC14My5sZXRzZW5jcnlwdC5vcmcwLwYIKwYBBQUHMAKGI2h0dHA6Ly9jZXJ0LmludC14My5sZXRzZW5' \
                  'jcnlwdC5vcmcvMIGOBgNVHREEgYYwgYOCZWVhZTAwZjY3NmZjMDczNTRjZDUwOTk5NGY5OTQ2OTU2LjQ2MjgwNWU2OTUwYWFjY' \
                  'mE0YzFiYzkwMjg4ODBlZmMyLjUzLTBiNS5maXJlZm94LjAuc3RhZ2UuZngtdHJhbnMubmV0ghppbnZhbGlkLnN0YWdlLmZ4LXR' \
                  'yYW5zLm5ldDCB/gYDVR0gBIH2MIHzMAgGBmeBDAECATCB5gYLKwYBBAGC3xMBAQEwgdYwJgYIKwYBBQUHAgEWGmh0dHA6Ly9jc' \
                  'HMubGV0c2VuY3J5cHQub3JnMIGrBggrBgEFBQcCAjCBngyBm1RoaXMgQ2VydGlmaWNhdGUgbWF5IG9ubHkgYmUgcmVsaWVkIHV' \
                  'wb24gYnkgUmVseWluZyBQYXJ0aWVzIGFuZCBvbmx5IGluIGFjY29yZGFuY2Ugd2l0aCB0aGUgQ2VydGlmaWNhdGUgUG9saWN5I' \
                  'GZvdW5kIGF0IGh0dHBzOi8vbGV0c2VuY3J5cHQub3JnL3JlcG9zaXRvcnkvMA0GCSqGSIb3DQEBCwUAA4IBAQA0z53WEnjjcAd' \
                  'DtLGD3xnvCYJSoIKV0MCeOfJ3VH+dJ0TQVDjDQftR9idjBLSjvtja1zG0PhZJIxbN4Fk+shbN8PZkMXrHAvbcdgM5CgdrCuPHU' \
                  'hPMsj+7ST0cgti15rTPYQwnTrfpTrjawks6fWWWhlc5u9iPzDDYJGquJz3zAIUHYQ5AKE4eVIx9POqYgf1ax5NsMdlXHoOn+UM' \
                  'MTgMU3mN3+ZvggkKF+swWF2yHGW/kq6uUUxTFNM2VbI1opy9TDFaFRveYZ6QsDXD/tOWRUJPfhlzEk19/T+G0TrxjIFVo6jToe' \
                  'NsMP7QklI6zrmGAuFSwnjGEFgMcankG3t1W", "MIIEkjCCA3qgAwIBAgIQCgFBQgAAAVOFc2oLheynCDANBgkqhkiG9w0BAQs' \
                  'FADA/MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMTDkRTVCBSb290IENBIFgzMB4XDTE2M' \
                  'DMxNzE2NDA0NloXDTIxMDMxNzE2NDA0NlowSjELMAkGA1UEBhMCVVMxFjAUBgNVBAoTDUxldCdzIEVuY3J5cHQxIzAhBgNVBAM' \
                  'TGkxldCdzIEVuY3J5cHQgQXV0aG9yaXR5IFgzMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnNMM8FrlLke3cl03g' \
                  '7NoYzDq1zUmGSXhvb418XCSL7e4S0EFq6meNQhY7LEqxGiHC6PjdeTm86dicbp5gWAf15Gan/PQeGdxyGkOlZHP/uaZ6WA8SMx' \
                  '+yk13EiSdRxta67nsHjcAHJyse6cF6s5K671B5TaYucv9bTyWaN8jKkKQDIZ0Z8h/pZq4UmEUEz9l6YKHy9v6Dlb2honzhT+Xh' \
                  'q+w3Brvaw2VFn3EK6BlspkENnWAa6xK8xuQSXgvopZPKiAlKQTGdMDQMc2PMTiVFrqoM7hD8bEfwzB/onkxEz0tNvjj/PIzark' \
                  '5McWvxI0NHWQWM6r6hCm21AvA2H3DkwIDAQABo4IBfTCCAXkwEgYDVR0TAQH/BAgwBgEB/wIBADAOBgNVHQ8BAf8EBAMCAYYwf' \
                  'wYIKwYBBQUHAQEEczBxMDIGCCsGAQUFBzABhiZodHRwOi8vaXNyZy50cnVzdGlkLm9jc3AuaWRlbnRydXN0LmNvbTA7BggrBgE' \
                  'FBQcwAoYvaHR0cDovL2FwcHMuaWRlbnRydXN0LmNvbS9yb290cy9kc3Ryb290Y2F4My5wN2MwHwYDVR0jBBgwFoAUxKexpHssc' \
                  'frb4UuQdf/EFWCFiRAwVAYDVR0gBE0wSzAIBgZngQwBAgEwPwYLKwYBBAGC3xMBAQEwMDAuBggrBgEFBQcCARYiaHR0cDovL2N' \
                  'wcy5yb290LXgxLmxldHNlbmNyeXB0Lm9yZzA8BgNVHR8ENTAzMDGgL6AthitodHRwOi8vY3JsLmlkZW50cnVzdC5jb20vRFNUU' \
                  'k9PVENBWDNDUkwuY3JsMB0GA1UdDgQWBBSoSmpjBH3duubRObemRWXv86jsoTANBgkqhkiG9w0BAQsFAAOCAQEA3TPXEfNjWDj' \
                  'dGBX7CVW+dla5cEilaUcne8IkCJLxWh9KEik3JHRRHGJouM2VcGfl96S8TihRzZvoroed6ti6WqEBmtzw3Wodatg+VyOeph4EY' \
                  'pr/1wXKtx8/wApIvJSwtmVi4MFU5aMqrSDE6ea73Mj2tcMyo5jMd6jmeWUHK8so/joWUoHOUgwuX4Po1QYz+3dszkDqMp4fklx' \
                  'BwXRsW10KXzPMTZ+sOPAveyxindmjkW8lGy+QsRlGPfZ+G6Z6h7mjem0Y+iWlkYcV4PIWL1iwBi8saCbGS5jN2p8M+X+Q7UNKE' \
                  'kROb3N6KOqkqm57TH2H3eDJAkSnh6/DNFu0Qg=="]}'

    config_vars = get_fake_config()
    req = get_chain(config_vars)

    assert req == correct_req


def test_post():
    correct_resp = '{"sct_version":0,"id":"pLkJkLQYWBSHuxOizGdwCjw1mAT5G9+443fNDsgN3BA=","timestamp":1502213019869,' \
                   '"extensions":"","signature":"BAMASDBGAiEAnZ6sJDFXEPxpbhVkiFusLCyoa+848vzGRJnh+2cSB84CIQCLXi3iEj' \
                   'K/uOcbrNnKAdds2wXV1v6xsn4II4jscs6bfQ=="}'

    log_url = 'https://ct.googleapis.com/pilot'
    req = '{"chain" : ["MIIFgTCCBGmgAwIBAgISA2RjCEL7JTlwJbUFmX95dBdhMA0GCSqGSIb3DQEBCwUAMEoxCzAJBgNVBAYTAlVTM' \
          'RYwFAYDVQQKEw1MZXQncyBFbmNyeXB0MSMwIQYDVQQDExpMZXQncyBFbmNyeXB0IEF1dGhvcml0eSBYMzAeFw0xNzA4MDgxNjE' \
          '3MDBaFw0xNzExMDYxNjE3MDBaMCUxIzAhBgNVBAMTGmludmFsaWQuc3RhZ2UuZngtdHJhbnMubmV0MIIBIjANBgkqhkiG9w0BA' \
          'QEFAAOCAQ8AMIIBCgKCAQEAtLKqMOVS3IPNVRMw+hzOTGyP+6VVyc4v3/w0Uaki1tTZX3o8u00+2iz8AxFA5Z/GvGsI5g3Djaw' \
          'Iy7ZOpB3oA9qsuRt0Gf7PTVyiPycHi3Wp8hU5PYzjenIwzJ6eXYPPiqQCuAxgygNE6PAcU8xMbAy94tokLzk1Dg6yzRJSDuR7p' \
          'wIWni6pMPK/xD6bamRxTsZx7A+I9NWYjG1B6+J1n0PQAovCGIY0m0hIvbCSmoTO63q8njJ+tHgwie7TFscVNca2qk0Q1+QXcLP' \
          'lJKV723wJMMdzzB+JHBvqX4ShImQaVHsLPwZM77K3d8PIfpRPhHhiy8/UPUo5n3yXQDKkdQIDAQABo4IChDCCAoAwDgYDVR0PA' \
          'QH/BAQDAgWgMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAAMB0GA1UdDgQWBBTSXXM+GndFLIt' \
          'squNZ1if5QuKGrzAfBgNVHSMEGDAWgBSoSmpjBH3duubRObemRWXv86jsoTBvBggrBgEFBQcBAQRjMGEwLgYIKwYBBQUHMAGGI' \
          'mh0dHA6Ly9vY3NwLmludC14My5sZXRzZW5jcnlwdC5vcmcwLwYIKwYBBQUHMAKGI2h0dHA6Ly9jZXJ0LmludC14My5sZXRzZW5' \
          'jcnlwdC5vcmcvMIGOBgNVHREEgYYwgYOCZWVhZTAwZjY3NmZjMDczNTRjZDUwOTk5NGY5OTQ2OTU2LjQ2MjgwNWU2OTUwYWFjY' \
          'mE0YzFiYzkwMjg4ODBlZmMyLjUzLTBiNS5maXJlZm94LjAuc3RhZ2UuZngtdHJhbnMubmV0ghppbnZhbGlkLnN0YWdlLmZ4LXR' \
          'yYW5zLm5ldDCB/gYDVR0gBIH2MIHzMAgGBmeBDAECATCB5gYLKwYBBAGC3xMBAQEwgdYwJgYIKwYBBQUHAgEWGmh0dHA6Ly9jc' \
          'HMubGV0c2VuY3J5cHQub3JnMIGrBggrBgEFBQcCAjCBngyBm1RoaXMgQ2VydGlmaWNhdGUgbWF5IG9ubHkgYmUgcmVsaWVkIHV' \
          'wb24gYnkgUmVseWluZyBQYXJ0aWVzIGFuZCBvbmx5IGluIGFjY29yZGFuY2Ugd2l0aCB0aGUgQ2VydGlmaWNhdGUgUG9saWN5I' \
          'GZvdW5kIGF0IGh0dHBzOi8vbGV0c2VuY3J5cHQub3JnL3JlcG9zaXRvcnkvMA0GCSqGSIb3DQEBCwUAA4IBAQA0z53WEnjjcAd' \
          'DtLGD3xnvCYJSoIKV0MCeOfJ3VH+dJ0TQVDjDQftR9idjBLSjvtja1zG0PhZJIxbN4Fk+shbN8PZkMXrHAvbcdgM5CgdrCuPHU' \
          'hPMsj+7ST0cgti15rTPYQwnTrfpTrjawks6fWWWhlc5u9iPzDDYJGquJz3zAIUHYQ5AKE4eVIx9POqYgf1ax5NsMdlXHoOn+UM' \
          'MTgMU3mN3+ZvggkKF+swWF2yHGW/kq6uUUxTFNM2VbI1opy9TDFaFRveYZ6QsDXD/tOWRUJPfhlzEk19/T+G0TrxjIFVo6jToe' \
          'NsMP7QklI6zrmGAuFSwnjGEFgMcankG3t1W", "MIIEkjCCA3qgAwIBAgIQCgFBQgAAAVOFc2oLheynCDANBgkqhkiG9w0BAQs' \
          'FADA/MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMTDkRTVCBSb290IENBIFgzMB4XDTE2M' \
          'DMxNzE2NDA0NloXDTIxMDMxNzE2NDA0NlowSjELMAkGA1UEBhMCVVMxFjAUBgNVBAoTDUxldCdzIEVuY3J5cHQxIzAhBgNVBAM' \
          'TGkxldCdzIEVuY3J5cHQgQXV0aG9yaXR5IFgzMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnNMM8FrlLke3cl03g' \
          '7NoYzDq1zUmGSXhvb418XCSL7e4S0EFq6meNQhY7LEqxGiHC6PjdeTm86dicbp5gWAf15Gan/PQeGdxyGkOlZHP/uaZ6WA8SMx' \
          '+yk13EiSdRxta67nsHjcAHJyse6cF6s5K671B5TaYucv9bTyWaN8jKkKQDIZ0Z8h/pZq4UmEUEz9l6YKHy9v6Dlb2honzhT+Xh' \
          'q+w3Brvaw2VFn3EK6BlspkENnWAa6xK8xuQSXgvopZPKiAlKQTGdMDQMc2PMTiVFrqoM7hD8bEfwzB/onkxEz0tNvjj/PIzark' \
          '5McWvxI0NHWQWM6r6hCm21AvA2H3DkwIDAQABo4IBfTCCAXkwEgYDVR0TAQH/BAgwBgEB/wIBADAOBgNVHQ8BAf8EBAMCAYYwf' \
          'wYIKwYBBQUHAQEEczBxMDIGCCsGAQUFBzABhiZodHRwOi8vaXNyZy50cnVzdGlkLm9jc3AuaWRlbnRydXN0LmNvbTA7BggrBgE' \
          'FBQcwAoYvaHR0cDovL2FwcHMuaWRlbnRydXN0LmNvbS9yb290cy9kc3Ryb290Y2F4My5wN2MwHwYDVR0jBBgwFoAUxKexpHssc' \
          'frb4UuQdf/EFWCFiRAwVAYDVR0gBE0wSzAIBgZngQwBAgEwPwYLKwYBBAGC3xMBAQEwMDAuBggrBgEFBQcCARYiaHR0cDovL2N' \
          'wcy5yb290LXgxLmxldHNlbmNyeXB0Lm9yZzA8BgNVHR8ENTAzMDGgL6AthitodHRwOi8vY3JsLmlkZW50cnVzdC5jb20vRFNUU' \
          'k9PVENBWDNDUkwuY3JsMB0GA1UdDgQWBBSoSmpjBH3duubRObemRWXv86jsoTANBgkqhkiG9w0BAQsFAAOCAQEA3TPXEfNjWDj' \
          'dGBX7CVW+dla5cEilaUcne8IkCJLxWh9KEik3JHRRHGJouM2VcGfl96S8TihRzZvoroed6ti6WqEBmtzw3Wodatg+VyOeph4EY' \
          'pr/1wXKtx8/wApIvJSwtmVi4MFU5aMqrSDE6ea73Mj2tcMyo5jMd6jmeWUHK8so/joWUoHOUgwuX4Po1QYz+3dszkDqMp4fklx' \
          'BwXRsW10KXzPMTZ+sOPAveyxindmjkW8lGy+QsRlGPfZ+G6Z6h7mjem0Y+iWlkYcV4PIWL1iwBi8saCbGS5jN2p8M+X+Q7UNKE' \
          'kROb3N6KOqkqm57TH2H3eDJAkSnh6/DNFu0Qg=="]}'

    with requests_mock.Mocker() as m:
        m.post(log_url + "/ct/v1/add-chain", text=correct_resp)
        resp = requests.post(log_url + "/ct/v1/add-chain", data=req, timeout=5).text

    assert resp == str(correct_resp)


def test_post_chain():
    correct_resp_list = [
        {'sct_version': 0, 'id': 'pLkJkLQYWBSHuxOizGdwCjw1mAT5G9+443fNDsgN3BA=', 'timestamp': 1502213019869,
         'extensions': '',
         'signature': 'BAMASDBGAiEAnZ6sJDFXEPxpbhVkiFusLCyoa+848vzGRJnh+2cSB84CIQCLXi3iEjK/uOcbrNnKAdds2wXV1v6xsn4II4jscs6bfQ=='},
        {'sct_version': 0, 'id': '7ku9t3XOYLrhQmkfq+GeZqMPfl+wctiDAMR7iXqo/cs=', 'timestamp': 1502310328978,
         'extensions': '',
         'signature': 'BAMARzBFAiBaFbWY+ni/dsYgmKoeLAb7VVIystdjDyL2v4QQB2JEnwIhAMp4++UrbnERi2WP1yLeT2ENx7aVPJbmGLyvTw1PFdL3'}]

    log_list = get_fake_config()["log_list"]
    req = '{"chain" : ["MIIFgTCCBGmgAwIBAgISA2RjCEL7JTlwJbUFmX95dBdhMA0GCSqGSIb3DQEBCwUAMEoxCzAJBgNVBAYTAlVTM' \
          'RYwFAYDVQQKEw1MZXQncyBFbmNyeXB0MSMwIQYDVQQDExpMZXQncyBFbmNyeXB0IEF1dGhvcml0eSBYMzAeFw0xNzA4MDgxNjE' \
          '3MDBaFw0xNzExMDYxNjE3MDBaMCUxIzAhBgNVBAMTGmludmFsaWQuc3RhZ2UuZngtdHJhbnMubmV0MIIBIjANBgkqhkiG9w0BA' \
          'QEFAAOCAQ8AMIIBCgKCAQEAtLKqMOVS3IPNVRMw+hzOTGyP+6VVyc4v3/w0Uaki1tTZX3o8u00+2iz8AxFA5Z/GvGsI5g3Djaw' \
          'Iy7ZOpB3oA9qsuRt0Gf7PTVyiPycHi3Wp8hU5PYzjenIwzJ6eXYPPiqQCuAxgygNE6PAcU8xMbAy94tokLzk1Dg6yzRJSDuR7p' \
          'wIWni6pMPK/xD6bamRxTsZx7A+I9NWYjG1B6+J1n0PQAovCGIY0m0hIvbCSmoTO63q8njJ+tHgwie7TFscVNca2qk0Q1+QXcLP' \
          'lJKV723wJMMdzzB+JHBvqX4ShImQaVHsLPwZM77K3d8PIfpRPhHhiy8/UPUo5n3yXQDKkdQIDAQABo4IChDCCAoAwDgYDVR0PA' \
          'QH/BAQDAgWgMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAAMB0GA1UdDgQWBBTSXXM+GndFLIt' \
          'squNZ1if5QuKGrzAfBgNVHSMEGDAWgBSoSmpjBH3duubRObemRWXv86jsoTBvBggrBgEFBQcBAQRjMGEwLgYIKwYBBQUHMAGGI' \
          'mh0dHA6Ly9vY3NwLmludC14My5sZXRzZW5jcnlwdC5vcmcwLwYIKwYBBQUHMAKGI2h0dHA6Ly9jZXJ0LmludC14My5sZXRzZW5' \
          'jcnlwdC5vcmcvMIGOBgNVHREEgYYwgYOCZWVhZTAwZjY3NmZjMDczNTRjZDUwOTk5NGY5OTQ2OTU2LjQ2MjgwNWU2OTUwYWFjY' \
          'mE0YzFiYzkwMjg4ODBlZmMyLjUzLTBiNS5maXJlZm94LjAuc3RhZ2UuZngtdHJhbnMubmV0ghppbnZhbGlkLnN0YWdlLmZ4LXR' \
          'yYW5zLm5ldDCB/gYDVR0gBIH2MIHzMAgGBmeBDAECATCB5gYLKwYBBAGC3xMBAQEwgdYwJgYIKwYBBQUHAgEWGmh0dHA6Ly9jc' \
          'HMubGV0c2VuY3J5cHQub3JnMIGrBggrBgEFBQcCAjCBngyBm1RoaXMgQ2VydGlmaWNhdGUgbWF5IG9ubHkgYmUgcmVsaWVkIHV' \
          'wb24gYnkgUmVseWluZyBQYXJ0aWVzIGFuZCBvbmx5IGluIGFjY29yZGFuY2Ugd2l0aCB0aGUgQ2VydGlmaWNhdGUgUG9saWN5I' \
          'GZvdW5kIGF0IGh0dHBzOi8vbGV0c2VuY3J5cHQub3JnL3JlcG9zaXRvcnkvMA0GCSqGSIb3DQEBCwUAA4IBAQA0z53WEnjjcAd' \
          'DtLGD3xnvCYJSoIKV0MCeOfJ3VH+dJ0TQVDjDQftR9idjBLSjvtja1zG0PhZJIxbN4Fk+shbN8PZkMXrHAvbcdgM5CgdrCuPHU' \
          'hPMsj+7ST0cgti15rTPYQwnTrfpTrjawks6fWWWhlc5u9iPzDDYJGquJz3zAIUHYQ5AKE4eVIx9POqYgf1ax5NsMdlXHoOn+UM' \
          'MTgMU3mN3+ZvggkKF+swWF2yHGW/kq6uUUxTFNM2VbI1opy9TDFaFRveYZ6QsDXD/tOWRUJPfhlzEk19/T+G0TrxjIFVo6jToe' \
          'NsMP7QklI6zrmGAuFSwnjGEFgMcankG3t1W", "MIIEkjCCA3qgAwIBAgIQCgFBQgAAAVOFc2oLheynCDANBgkqhkiG9w0BAQs' \
          'FADA/MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNVBAMTDkRTVCBSb290IENBIFgzMB4XDTE2M' \
          'DMxNzE2NDA0NloXDTIxMDMxNzE2NDA0NlowSjELMAkGA1UEBhMCVVMxFjAUBgNVBAoTDUxldCdzIEVuY3J5cHQxIzAhBgNVBAM' \
          'TGkxldCdzIEVuY3J5cHQgQXV0aG9yaXR5IFgzMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnNMM8FrlLke3cl03g' \
          '7NoYzDq1zUmGSXhvb418XCSL7e4S0EFq6meNQhY7LEqxGiHC6PjdeTm86dicbp5gWAf15Gan/PQeGdxyGkOlZHP/uaZ6WA8SMx' \
          '+yk13EiSdRxta67nsHjcAHJyse6cF6s5K671B5TaYucv9bTyWaN8jKkKQDIZ0Z8h/pZq4UmEUEz9l6YKHy9v6Dlb2honzhT+Xh' \
          'q+w3Brvaw2VFn3EK6BlspkENnWAa6xK8xuQSXgvopZPKiAlKQTGdMDQMc2PMTiVFrqoM7hD8bEfwzB/onkxEz0tNvjj/PIzark' \
          '5McWvxI0NHWQWM6r6hCm21AvA2H3DkwIDAQABo4IBfTCCAXkwEgYDVR0TAQH/BAgwBgEB/wIBADAOBgNVHQ8BAf8EBAMCAYYwf' \
          'wYIKwYBBQUHAQEEczBxMDIGCCsGAQUFBzABhiZodHRwOi8vaXNyZy50cnVzdGlkLm9jc3AuaWRlbnRydXN0LmNvbTA7BggrBgE' \
          'FBQcwAoYvaHR0cDovL2FwcHMuaWRlbnRydXN0LmNvbS9yb290cy9kc3Ryb290Y2F4My5wN2MwHwYDVR0jBBgwFoAUxKexpHssc' \
          'frb4UuQdf/EFWCFiRAwVAYDVR0gBE0wSzAIBgZngQwBAgEwPwYLKwYBBAGC3xMBAQEwMDAuBggrBgEFBQcCARYiaHR0cDovL2N' \
          'wcy5yb290LXgxLmxldHNlbmNyeXB0Lm9yZzA8BgNVHR8ENTAzMDGgL6AthitodHRwOi8vY3JsLmlkZW50cnVzdC5jb20vRFNUU' \
          'k9PVENBWDNDUkwuY3JsMB0GA1UdDgQWBBSoSmpjBH3duubRObemRWXv86jsoTANBgkqhkiG9w0BAQsFAAOCAQEA3TPXEfNjWDj' \
          'dGBX7CVW+dla5cEilaUcne8IkCJLxWh9KEik3JHRRHGJouM2VcGfl96S8TihRzZvoroed6ti6WqEBmtzw3Wodatg+VyOeph4EY' \
          'pr/1wXKtx8/wApIvJSwtmVi4MFU5aMqrSDE6ea73Mj2tcMyo5jMd6jmeWUHK8so/joWUoHOUgwuX4Po1QYz+3dszkDqMp4fklx' \
          'BwXRsW10KXzPMTZ+sOPAveyxindmjkW8lGy+QsRlGPfZ+G6Z6h7mjem0Y+iWlkYcV4PIWL1iwBi8saCbGS5jN2p8M+X+Q7UNKE' \
          'kROb3N6KOqkqm57TH2H3eDJAkSnh6/DNFu0Qg=="]}'

    resp_list = post_chain(log_list, req)

    assert resp_list == correct_resp_list
