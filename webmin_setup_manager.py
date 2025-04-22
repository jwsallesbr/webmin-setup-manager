#!/usr/bin/env python3

import os
import subprocess
import sys
import shutil

def check_root():
    if os.geteuid() != 0:
        print("Este script deve ser executado como root ou com privilégios de sudo.")
        sys.exit(1)

def get_distro():
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("ID="):
                        distro = line.strip().split("=")[1].replace('"', '').lower()
                        if distro in ["rocky"]:
                            return "centos"
                        return distro
        return None
    except Exception as e:
        print(f"Erro ao detectar a distribuição: {e}")
        sys.exit(1)

def run_command(command, description=None, exit_on_error=False, input_text=None):
    if description:
        print(f"[*] {description}")
    try:
        if input_text:
            process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(input=input_text.encode())
            return process.returncode == 0
        else:
            result = subprocess.run(command, shell=True, check=False, 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                error_msg = result.stderr.decode().strip()
                if error_msg:
                    print(f"[!] Erro: {error_msg}")
                if exit_on_error:
                    sys.exit(result.returncode)
                return False
            return True
    except Exception as e:
        print(f"[!] Exceção ao executar comando: {e}")
        if exit_on_error:
            sys.exit(1)
        return False

def is_webmin_installed():
    distro = get_distro()
    if distro in ["ubuntu", "debian"]:
        return run_command("dpkg -l webmin 2>/dev/null | grep -q '^ii'", 
                         "Verificando pacote webmin")
    elif distro in ["centos", "fedora", "rocky"]:
        return run_command("rpm -q webmin >/dev/null 2>&1", 
                         "Verificando pacote webmin")
    return os.path.exists("/usr/share/webmin") or os.path.exists("/etc/webmin")

def is_webmin_active():
    result = subprocess.run("systemctl is-active webmin", shell=True, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def is_webmin_enabled():
    result = subprocess.run("systemctl is-enabled webmin", shell=True, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def manage_webmin_service():
    active = is_webmin_active()
    enabled = is_webmin_enabled()
    
    ip_address = subprocess.getoutput("hostname -I | awk '{print $1}'")
    
    if not active:
        resposta = input("[?] Webmin não está ativo. Deseja ativá-lo? (s/n): ").strip().lower()
        if resposta == "s":
            run_command("systemctl enable --now webmin", "Ativando webmin")
            print("=" * 40)
            print(f"Webmin ativado! Acesse: https://{ip_address}:10000")
            print("=" * 40)
    else:
        print("[*] Webmin já está ativo e rodando")
        print(f"[*] Acesse: https://{ip_address}:10000")
        resposta = input("[?] Deseja reiniciar o serviço? (s/n): ").strip().lower()
        if resposta == "s":
            run_command("systemctl restart webmin", "Reiniciando webmin")

def install_webmin(distro):
    print("=" * 40)
    print("Instalando o Webmin...")
    print("=" * 40)

    # Baixar o script de configuração do repositório
    success = run_command("curl -o webmin-setup-repo.sh https://raw.githubusercontent.com/webmin/webmin/master/webmin-setup-repo.sh", 
                        "Baixando script de instalação")
    if not success:
        print("[!] Falha ao baixar o script de instalação")
        return False

    # Executar o script com confirmação automática (y + Enter)
    success = run_command("sh webmin-setup-repo.sh", "Configurando repositório", input_text="y\n")
    if not success:
        print("[!] Falha ao configurar o repositório")
        return False

    # Instalar o Webmin
    if distro in ["ubuntu", "debian"]:
        success = run_command("apt-get update", "Atualizando repositórios")
        success &= run_command("apt-get -y install webmin", "Instalando webmin")
    elif distro in ["centos", "rocky", "fedora"]:
        success = run_command("yum -y install webmin", "Instalando webmin")

    if success:
        manage_webmin_service()
        return True
    else:
        print("[!] Falha na instalação do Webmin")
        return False

def remove_webmin(distro):
    print("=" * 40)
    print("Removendo o Webmin...")
    print("=" * 40)
    
    run_command("systemctl stop webmin", "Parando serviço")
    run_command("systemctl disable webmin", "Desativando serviço")
    
    if distro in ["ubuntu", "debian"]:
        run_command("apt-get -y remove --purge webmin", "Removendo pacote principal")
        run_command("apt-get -y autoremove", "Limpando dependências")
    elif distro in ["centos", "rocky", "fedora"]:
        run_command("yum -y remove webmin", "Removendo pacote principal")
        run_command("yum -y autoremove", "Limpando dependências")
    
    # Lista de diretórios a serem removidos
    webmin_dirs = [
        "/etc/webmin",
        "/usr/share/webmin",
        "/var/webmin"
    ]
    
    existing_dirs = [d for d in webmin_dirs if os.path.exists(d)]
    
    if existing_dirs:
        print("\n[!] Os seguintes diretórios foram encontrados:")
        for directory in existing_dirs:
            print(f"    - {directory}")
        
        resposta = input("\n[?] Deseja remover estes diretórios? (s/n): ").strip().lower()
        if resposta == "s":
            for directory in existing_dirs:
                try:
                    shutil.rmtree(directory)
                    print(f"[+] Removido diretório: {directory}")
                except Exception as e:
                    print(f"[!] Erro ao remover {directory}: {e}")
        else:
            print("[*] Diretórios não foram removidos.")
    else:
        print("[*] Nenhum diretório encontrado.")

    print("=" * 40)
    print("Remoção concluída!")
    print("=" * 40)

def main():
    check_root()
    distro = get_distro()

    if not distro:
        print("[!] Não foi possível detectar a distribuição")
        sys.exit(1)

    if distro not in ["debian", "ubuntu", "centos", "rocky", "fedora"]:
        print(f"[!] Distribuição não suportada: {distro}")
        sys.exit(1)

    if is_webmin_installed():
        print("[*] Webmin está instalado")
        resposta = input("[?] Deseja (1) remover, (2) ativar ou (3) cancelar? [1/2/3]: ").strip()
        
        if resposta == "1":
            remove_webmin(distro)
        elif resposta == "2":
            manage_webmin_service()
        else:
            print("[*] Operação cancelada.")
    else:
        resposta = input("[?] Webmin não está instalado. Deseja instalá-lo? (s/n): ").strip().lower()
        if resposta == "s":
            install_webmin(distro)
        else:
            print("[*] Operação cancelada.")

if __name__ == "__main__":
    main()