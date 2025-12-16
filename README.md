# Zabbix-MT
## INSTALL
### Install Python/venv
$ sudo dnf -y install bzip2-devel gcc gcc-c++ git libffi-devel make openssl-devel readline-devel sqlite-devel zlib-devel xz xz-devel patch

$ sudo -E PYENV_ROOT=/usr/local/pyenv /usr/local/pyenv/bin/pyenv install 3.11.9

### Install zabbix-MT
$ sudo tar xvzf Zabbix-MT-0.5.tar.gz -C /usr/lib/zabbix/externalscripts/

$ sudo /usr/local/pyenv/versions/3.11.9/bin/python -m venv /usr/lib/zabbix/externalscripts/Zabbix-MT-0.5/venv

$ sudo /usr/lib/zabbix/externalscripts/Zabbix-MT-0.5/install.sh

$ sudo -u zabbix /usr/lib/zabbix/externalscripts/zabbix-MT.sh
{"data": []}
