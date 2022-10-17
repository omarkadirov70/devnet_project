import concurrent.futures
from netmiko import ConnectHandler

def script(router):
    USER ='test'
    PASSWORD = 'test'
    try:
        
        router = {'device_type': 'cisco_ios', 'ip': router, 'username': USER, 'password': PASSWORD, 'verbose': False, 'fast_cli': False,}
        ssh = ConnectHandler(**router)

        s=ssh.send_command('sh ip int br')

        hostname = ssh.find_prompt()[:-1] 

        print(f"""--- {hostname} ---
{s}""")
    except Exception as err:
        exception_type = type(err).__name__
        print(f""" - - - - - - - - - {exception_type} - - - - - - - - - """)

    
routers = ['192.168.126.139', '10.0.0.2', '10.0.0.3', '10.0.0.4']

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exe:
    res = exe.map(script, routers)