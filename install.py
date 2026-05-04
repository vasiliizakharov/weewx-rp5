"""WeeWX extension installer for weewx-rp5."""
from weecfg.extension import ExtensionInstaller


def loader():
    return RP5Installer()


class RP5Installer(ExtensionInstaller):
    def __init__(self):
        super().__init__(
            version="1.0.0",
            name="rp5",
            description="Upload archive weather data to rp5.ru via sgate API",
            author="Vasilii Zakharov (original by Sapegin Oleg)",
            author_email="vasiliiazakharov@gmail.com",
            restful_services="user.rp5.StdRP5",
            config={
                "StdRESTful": {
                    "RP5": {
                        "enable": "false",
                        "api_key": "ENTER_RP5_API_KEY_HERE",
                        "server_url": "https://sgate.rp5.ru",
                        "post_interval": "60",
                        "max_tries": "3",
                        "timeout": "10",
                    }
                }
            },
            files=[("bin/user", ["bin/user/rp5.py"])],
        )
