import re
import time
import os.path
import openpyxl
import threading
from queue import Queue
import concurrent.futures
from flask import Flask, render_template, request
from flask_wtf import FlaskForm
from wtforms import FileField, SubmitField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired
from netmiko import ConnectHandler

UPLOAD_FOLDER = 'static/uploads/'
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/files'


class UploadFileForm(FlaskForm):
    file = FileField("File", validators=[InputRequired()])
    submit = SubmitField("Upload File")


@app.route('/', methods=["POST", "GET"])
def index():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        with open('login.txt', 'w') as file:
            file.write(f"""{u}
{p}""")

        return render_template('index.html')
    else:
        return render_template('index.html')


@app.route('/send', methods=["POST", "GET"])
def send():
    if request.method == 'POST':
        with open('login.txt', 'r') as file:
            x = file.readlines()
            u = x[0].strip()
            p = x[1].strip()

        ip_add = request.form['ip_add']
        router = {'device_type': 'cisco_ios', 'ip': f'{ip_add}', 'username': f'{u}', 'password': f'{p}',
                  'verbose': False, 'fast_cli': False, }
        ssh_session = ConnectHandler(**router)
        output = ssh_session.send_command(f"""{request.form['command']}""").splitlines()
        ssh_session.disconnect()

    else:
        output = ' '

    return render_template('send.html', output=output)


@app.route('/upload', methods=["POST", "GET"])
def upload():
    form = UploadFileForm()
    if form.validate_on_submit():
        file = form.file.data
        file.save(os.path.join(os.path.abspath(os.path.dirname(__file__)), app.config['UPLOAD_FOLDER'],
                               secure_filename(file.filename)))
        out = "Uploaded!"
    else:
        out = ' '
    return render_template('upload.html', form=form, out=out)


@app.route('/execute', methods=["POST", "GET"])
def execute():
    dir_list = os.listdir(f"""{os.path.dirname(os.path.abspath(__file__))}/static/files""")
    if request.method == 'POST':
        try:
            with open('login.txt', 'r') as file:
                x = file.readlines()
                u = x[0].strip()
                p = x[1].strip()

            if os.path.exists('vlan_counter.txt') == False:
                with open('vlan_counter.txt', 'w') as file:
                    file.write('199')

            else:
                with open('vlan_counter.txt', 'r') as f:
                    old_data = f.readlines()

                    if int(old_data[0]) <= 300:
                        new_data = int(old_data[0]) + 1
                        with open('vlan_counter.txt', 'w') as nf:
                            nf.write(str(new_data))

            with open('vlan_counter.txt', 'r') as cr:
                data = cr.readlines()
                crypto_number = int(data[0])

            with open('login.txt', 'r') as file:
                x = file.readlines()
                u = x[0].strip()
                p = x[1].strip()

            file = request.form['file']
            with open(f"""{os.path.dirname(os.path.abspath(__file__))}/static/files/{file}""", 'r') as ip_txt:
                x = ip_txt.readlines()

            r = []

            for i in x:
                r.append(i.strip())

            for add in r:
                router = {'device_type': 'cisco_ios', 'ip': f'{add}', 'username': f'{u}', 'password': f'{p}',
                          'verbose': False, 'fast_cli': False, }
                ssh = ConnectHandler(**router)
                s = ssh.send_command('sh run')

                txt = s.split()

                i = 0

                while i < len(txt):
                    if txt[i] == "interface" and txt[i + 1] == "Vlan2":
                        vlg = txt[i + 4].split('.')
                        ind = vlg.index(vlg[3])
                        minus = int(vlg[3]) - 1
                        vlg = vlg[:ind] + [str(minus)]
                        vlan_g = '.'.join(map(str, vlg))

                    if txt[i] == "interface" and txt[i + 1] == "Vlan2":
                        vl_mask = txt[i + 5]

                    if txt[i] == "hostname":
                        hostname = txt[i + 1]

                    if txt[i] == "interface" and txt[i + 1] == "Tunnel1":
                        tunnel_ip = txt[i + 6]

                    if txt[i] == "interface" and txt[i + 1] == "Loopback100":
                        lb100_ip = txt[i + 4]
                    i += 1

                conf = f"""
                            # Router Cisco
                            !
                            ip access-list extended PCIDSS
                            permit ip {vlan_g} 0.0.0.7  host 10.1.1.100
                            permit ip {vlan_g} 0.0.0.7  host 10.1.1.102
                            permit ip {vlan_g} 0.0.0.7  host 10.2.87.27
                            permit ip {vlan_g} 0.0.0.7  host 10.2.87.25
        
                            crypto isakmp policy 10
                            encr aes 256
                            authentication pre-share
                            group 5
                            crypto isakmp key {hostname} address 10.199.0.36
                            !
                            crypto ipsec security-association lifetime seconds 86400
                            crypto ipsec transform-set ATM esp-aes 256 esp-sha-hmac
                            !
                            crypto map PCIDSS local-address Loopback100
                            crypto map PCIDSS 10 ipsec-isakmp
                            set peer 10.199.0.36
                            set transform-set ATM
                            match address PCIDSS
        
        
                            # Маршрут на ASA-ATM-VPN, next hop меняется
                            !
                            ip route 10.199.0.36 255.255.255.255 {tunnel_ip}
                            !
        
                            # Настройка Cisco ASA-ATM-VPN 5555 10.9.0.36 (Management 10.2.25.131)
                            !
                            # Настройка access-list, меняется подсеть и название ACL (номер банкомата)
                            !
                            access-list {hostname}-PCIDSS extended permit ip host 10.1.1.100 {vlan_g} {vl_mask}
                            access-list {hostname}-PCIDSS extended permit ip host 10.1.1.102 {vlan_g} {vl_mask}
                            access-list {hostname}-PCIDSS extended permit ip host 10.2.87.27 {vlan_g} {vl_mask}
                            access-list {hostname}-PCIDSS extended permit ip host 10.2.87.25 {vlan_g} {vl_mask}
                            !
                            # Настройка crypto-map, меняется адрес PEER, название ACL и номер - увеличение на 1 - 11, 12 и т.д.
                            !
                            crypto map outside_map {crypto_number} match address {hostname}-PCIDSS
                            crypto map outside_map 10 set peer {lb100_ip}
                            crypto map outside_map 10 set ikev1 transform-set AES256-SHA256
                            !
                            # Настройка tunnel-group, меняется адрес PEER и ikev1 pre-shared-key (одинаковый как на банкомате)
                            tunnel-group {lb100_ip} type ipsec-l2l
                            tunnel-group {lb100_ip} ipsec-attributes
                            ikev1 pre-shared-key {hostname}
                            isakmp keepalive threshold 60 retry 10
                        """

                lines = conf.splitlines()
                hostname = ssh.find_prompt()[:-1]
                file_name = f"""{hostname}.txt"""
                with open(file_name, 'w') as file:
                    for line in lines:
                        file.write(line.strip() + '\n')

        except Exception as err:
            exception_type = type(err).__name__

            print(f"""_________________________{exception_type}_________________________""")

        outp = 'DONE'

    else:
        outp = ' '

    return render_template('execute.html', outp=outp, dir_list=dir_list)


if __name__ == '__main__':
    app.run(debug=True)
