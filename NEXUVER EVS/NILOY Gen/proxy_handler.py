import os
import random
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urlparse


def parse_proxy(proxy_string: str) -> Optional[Dict]:
    if not proxy_string:
        return None
    
    proxy_string = proxy_string.strip()
    
    if '://' not in proxy_string:
        proxy_string = 'socks5://' + proxy_string
    
    try:
        parsed = urlparse(proxy_string)
        proxy_type = parsed.scheme.lower()
        host = parsed.hostname
        port = parsed.port
        
        if not host or not port:
            return None
        
        full_url = proxy_string
        masked_url = proxy_string
        
        if parsed.username and parsed.password:
            masked_url = f"{proxy_type}://{parsed.username}:***@{host}:{port}"
        
        return {
            'type': proxy_type,
            'host': host,
            'port': port,
            'full_url': full_url,
            'masked_url': masked_url,
        }
    except Exception:
        return None


def get_browser_proxy_args(proxy_config: Dict) -> List[str]:
    args = []
    if not proxy_config:
        return args
    
    full_url = proxy_config.get('full_url')
    if full_url:
        args.append(f'--proxy-server={full_url}')
        args.append('--proxy-bypass-list=<-loopback>')
    
    return args


def get_session_proxy(proxy_config: Dict) -> Optional[Dict]:
    if not proxy_config:
        return None
    
    full_url = proxy_config.get('full_url')
    if full_url:
        return {'http': full_url, 'https': full_url}
    
    return None


def load_proxies(proxy_file: str = "input/proxies.txt", enabled: bool = True) -> List[Dict]:
    if not enabled:
        return []
    
    proxy_path = Path(proxy_file)
    
    if not proxy_path.exists():
        print(f"[WARNING] Proxy file not found: {proxy_file}")
        return []
    
    try:
        proxies = []
        with open(proxy_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parsed = parse_proxy(line)
                    if parsed:
                        proxies.append(parsed)
        
        
        return proxies
    except Exception as e:
        print(f"[ERROR] Error loading proxies: {e}")
        return []


def rotate_proxy(proxy_list: List[Dict], current_index: int = None) -> tuple:
    if not proxy_list:
        return None, 0
    
    if current_index is None:
        current_index = random.randint(0, len(proxy_list) - 1)
    else:
        current_index = (current_index + 1) % len(proxy_list)
    
    return proxy_list[current_index], current_index


def get_random_proxy(proxy_list: List[Dict]) -> Optional[Dict]:
    if not proxy_list:
        return None
    
    return random.choice(proxy_list)


import threading

_file_lock = threading.Lock()


def remove_proxy(proxy_list: List[Dict], proxy_config: Dict, proxy_file: str = "input/proxies.txt"):

    if not proxy_config:
        return


    full_url = proxy_config.get('full_url', '')
    try:
        proxy_list[:] = [p for p in proxy_list if p.get('full_url') != full_url]
    except Exception:
        pass


    proxy_path = Path(proxy_file)
    if not proxy_path.exists():
        return

    with _file_lock:
        try:
            with open(proxy_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            new_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    new_lines.append(line)
                    continue

                parsed = parse_proxy(stripped)
                if parsed and parsed.get('full_url') == full_url:
                    continue
                new_lines.append(line)

            with open(proxy_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            print(f"[PROXY] Removed used proxy from {proxy_file} ({len(lines) - len(new_lines)} removed, {sum(1 for l in new_lines if l.strip() and not l.strip().startswith('#'))} remaining)")
        except Exception as e:
            print(f"[WARNING] Failed to remove proxy from file: {e}")


def test_proxy(proxy_config: Dict, test_url: str = "https://api.ipify.org", timeout: int = 10) -> Optional[str]:
    if not proxy_config:
        return None
    
    try:
        import requests
        proxies = get_session_proxy(proxy_config)
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        if response.status_code == 200:
            return response.text.strip()
    except Exception:
        pass
    
    return None


if __name__ == "__main__":
    proxy = parse_proxy("user:pass@192.168.1.1:8080")
    print(f"Parsed proxy: {proxy}")
    
    browser_args = get_browser_proxy_args(proxy)
    print(f"Browser args: {browser_args}")
    
    session_proxy = get_session_proxy(proxy)
    print(f"Session proxy: {session_proxy}")
    
    proxies = load_proxies("input/proxies.txt", enabled=True)
    print(f"Loaded {len(proxies)} proxies")
    
    if proxies:
        current_proxy, idx = rotate_proxy(proxies)
        print(f"Current proxy: {current_proxy.get('masked_url')}")
        
        next_proxy, new_idx = rotate_proxy(proxies, idx)
        print(f"Next proxy: {next_proxy.get('masked_url')}")
    
    if proxies:
        ip = test_proxy(proxies[0])
        if ip:
            print(f"Proxy IP: {ip}")
        else:
            print("Proxy test failed")
    
    print("\n--- Integration Example ---")
    print("""
    # In your main code:
    
    from proxy_handler import load_proxies, get_browser_proxy_args, rotate_proxy
    
    all_proxies = load_proxies("input/proxies.txt", config["proxy"]["enabled"])
    
    proxy_config = all_proxies[worker_index % len(all_proxies)] if all_proxies else None
    
    browser_args = []
    if proxy_config:
        browser_args.extend(get_browser_proxy_args(proxy_config))
    
    session = requests.Session()
    if proxy_config:
        session.proxies.update(get_session_proxy(proxy_config))
    """)