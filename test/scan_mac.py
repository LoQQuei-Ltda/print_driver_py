import argparse
import platform
import subprocess
import re
from scapy.all import srp, Ether, ARP

def get_mac_address(ip_address):
    """
    Obtém o endereço MAC de um IP específico usando ARP.
    """
    try:
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=ip_address), timeout=2, verbose=False)
        if ans:
            return ans[0][1].hwsrc
    except Exception as e:
        print(f"Erro ao obter MAC para {ip_address}: {e}")
    return None

def scan_network_for_mac(target_mac, network_prefix="192.168.1.", start_ip=1, end_ip=254):
    """
    Varre a rede local em busca de um endereço MAC específico.
    """
    print(f"Procurando pelo MAC: {target_mac} na rede {network_prefix}x ...")
    found_devices = []
    target_mac = target_mac.lower()

    for i in range(start_ip, end_ip + 1):
        ip = f"{network_prefix}{i}"
        print(f"Verificando IP: {ip}")
        mac = get_mac_address(ip)
        if mac:
            print(f"  IP: {ip} - MAC: {mac}")
            if mac.lower() == target_mac:
                print(f"*** Dispositivo ENCONTRADO! IP: {ip}, MAC: {mac} ***")
                found_devices.append({"ip": ip, "mac": mac})
        # Adiciona uma pequena pausa para não sobrecarregar a rede ou dispositivos
        # import time
        # time.sleep(0.05)


    if not found_devices:
        print(f"Nenhum dispositivo encontrado com o MAC: {target_mac}")
    else:
        print("\nDispositivos encontrados com o MAC especificado:")
        for device in found_devices:
            print(f"  IP: {device['ip']}, MAC: {device['mac']}")
    return found_devices

def get_default_network_prefix():
    """
    Tenta obter o prefixo de rede padrão de forma rudimentar.
    Pode precisar de ajustes dependendo da configuração da rede.
    """
    system = platform.system().lower()
    try:
        if system == "windows":
            process = subprocess.Popen(["ipconfig"], stdout=subprocess.PIPE)
            stdout, _ = process.communicate()
            output = stdout.decode('cp850', errors='ignore') # Tenta com cp850, comum em PT-BR Windows
            match = re.search(r"Gateway Padrão[.\s]+: (\d{1,3}\.\d{1,3}\.\d{1,3})\.", output)
            if match:
                return ".".join(match.group(1).split('.')[:3]) + "."
            match = re.search(r"Default Gateway[.\s]+: (\d{1,3}\.\d{1,3}\.\d{1,3})\.", output) # Inglês
            if match:
                return ".".join(match.group(1).split('.')[:3]) + "."
        elif system == "linux" or system == "darwin": # macOS
            process = subprocess.Popen(["ip", "route"], stdout=subprocess.PIPE)
            stdout, _ = process.communicate()
            output = stdout.decode()
            match = re.search(r"default via (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", output)
            if match:
                return ".".join(match.group(1).split('.')[:3]) + "."
    except FileNotFoundError:
        print("Comando 'ipconfig' ou 'ip route' não encontrado. Usando prefixo padrão.")
    except Exception as e:
        print(f"Erro ao tentar obter o prefixo de rede: {e}. Usando prefixo padrão.")

    # Fallback para um prefixo comum
    print("Não foi possível determinar o prefixo de rede automaticamente. Usando 192.168.1.")
    return "192.168.1."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encontra dispositivos na rede local com um endereço MAC específico.")
    parser.add_argument("mac_address", help="O endereço MAC a ser procurado (ex: 00:1A:2B:3C:4D:5E)")
    parser.add_argument("--network", help="O prefixo da rede a ser varrida (ex: 192.168.0.)")
    parser.add_argument("--start_ip", type=int, default=1, help="IP inicial para varredura (ex: 1)")
    parser.add_argument("--end_ip", type=int, default=254, help="IP final para varredura (ex: 254)")

    args = parser.parse_args()

    network_prefix = args.network
    if not network_prefix:
        network_prefix = get_default_network_prefix()

    # Validação simples do formato do MAC (XX:XX:XX:XX:XX:XX)
    if not re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", args.mac_address):
        print("Formato de endereço MAC inválido. Use XX:XX:XX:XX:XX:XX")
    else:
        scan_network_for_mac(args.mac_address, network_prefix, args.start_ip, args.end_ip)