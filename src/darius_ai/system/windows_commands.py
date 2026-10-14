"""
windows_commands.py — v2.1 — CORRECCIÓN DE BUGS
================================================
Cambio principal: cutoff del fuzzy subido de 0.52 → 0.72 para SYSTEM_ACTIONS.
Esto evita que "cuanto es 2x2" (score 0.59) matchee "ver espacio en disco".
WINDOWS_COMMANDS mantiene 0.65 porque sus aliases son más cortos y específicos.
"""

import logging
import os
import re
import subprocess
from difflib import SequenceMatcher

_WINDIR = os.environ.get("SYSTEMROOT", "C:\\Windows")
_PS = _WINDIR + "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
_CMD = _WINDIR + "\\System32\\cmd.exe"
_MMC = _WINDIR + "\\System32\\mmc.exe"
_CONTROL = _WINDIR + "\\System32\\control.exe"

log = logging.getLogger("DARIUS.WinCMD")


# ═════════════════════════════════════════════════════════════════════════════
#  TIPO A — ABRIR VENTANAS / PANELES
# ═════════════════════════════════════════════════════════════════════════════

WINDOWS_COMMANDS: dict[str, dict] = {
    "configuracion de red": {
        "cmd": "ms-settings:network",
        "aliases": [
            "configuraciones de red",
            "ajustes de red",
            "red e internet",
            "configurar red",
            "opciones de red",
            "conexiones de red",
            "configuracion de internet",
            "ajustes de internet",
            "internet y red",
            "red wifi",
            "configuracion wifi",
        ],
        "desc": "Configuración de Red e Internet",
    },
    "wifi": {
        "cmd": "ms-settings:network-wifi",
        "aliases": ["configuracion wifi", "ajustes wifi", "redes wifi", "conectar wifi"],
        "desc": "Configuración WiFi",
    },
    "vpn": {
        "cmd": "ms-settings:network-vpn",
        "aliases": ["configurar vpn", "ajustes vpn"],
        "desc": "Configuración VPN",
    },
    "ethernet": {
        "cmd": "ms-settings:network-ethernet",
        "aliases": ["conexion ethernet", "cable de red", "red cableada"],
        "desc": "Configuración Ethernet",
    },
    "proxy": {
        "cmd": "ms-settings:network-proxy",
        "aliases": ["configuracion proxy", "ajustes proxy"],
        "desc": "Configuración de Proxy",
    },
    "estado de red": {
        "cmd": "ms-settings:network-status",
        "aliases": ["estado de conexion", "ver estado de red", "diagnostico de red"],
        "desc": "Estado de la red",
    },
    "adaptadores de red": {
        "cmd": "ncpa.cpl",
        "aliases": ["ver adaptadores", "conexiones de red clasico", "propiedades de red", "adaptador de red"],
        "desc": "Conexiones de red (adaptadores)",
    },
    "aplicaciones y caracteristicas": {
        "cmd": "ms-settings:appsfeatures",
        "aliases": [
            "aplicaciones y características",
            "apps y caracteristicas",
            "apps instaladas",
            "programas instalados",
            "desinstalar programas",
            "administrar aplicaciones",
            "gestionar apps",
            "ver aplicaciones",
            "aplicaciones del sistema",
            "lista de aplicaciones",
            "aplicaciones y caracteristicas de windows",
        ],
        "desc": "Aplicaciones y características",
    },
    "aplicaciones predeterminadas": {
        "cmd": "ms-settings:defaultapps",
        "aliases": ["apps predeterminadas", "programas predeterminados", "aplicaciones por defecto"],
        "desc": "Aplicaciones predeterminadas",
    },
    "inicio automatico": {
        "cmd": "ms-settings:startupapps",
        "aliases": ["aplicaciones de inicio", "apps al iniciar", "programas de inicio", "inicio de windows"],
        "desc": "Aplicaciones de inicio",
    },
    "caracteristicas opcionales": {
        "cmd": "ms-settings:optionalfeatures",
        "aliases": ["funciones opcionales", "características de windows", "agregar características"],
        "desc": "Características opcionales de Windows",
    },
    "programas y caracteristicas clasico": {
        "cmd": "appwiz.cpl",
        "aliases": ["desinstalar programas clasico", "agregar o quitar programas", "appwiz"],
        "desc": "Programas y características (Panel de Control)",
    },
    "configuracion": {
        "cmd": "ms-settings:",
        "aliases": ["ajustes de windows", "settings de windows", "opciones del sistema"],
        "desc": "Configuración de Windows",
    },
    "pantalla": {
        "cmd": "ms-settings:display",
        "aliases": [
            "configuracion de pantalla",
            "ajustes de pantalla",
            "resolucion de pantalla",
            "brillo de pantalla",
            "configurar monitor",
        ],
        "desc": "Configuración de pantalla",
    },
    "sonido": {
        "cmd": "ms-settings:sound",
        "aliases": [
            "configuracion de sonido",
            "ajustes de audio",
            "volumen del sistema",
            "dispositivos de audio",
            "salida de audio",
            "entrada de audio",
        ],
        "desc": "Configuración de sonido",
    },
    "notificaciones": {
        "cmd": "ms-settings:notifications",
        "aliases": [
            "configuracion de notificaciones",
            "ajustes de notificaciones",
            "alertas del sistema",
            "centro de notificaciones",
        ],
        "desc": "Notificaciones y acciones",
    },
    "energia": {
        "cmd": "ms-settings:powersleep",
        "aliases": ["configuracion de energia", "plan de energia", "ahorro de bateria", "opciones de energia"],
        "desc": "Energía y suspensión",
    },
    "almacenamiento": {
        "cmd": "ms-settings:storagesense",
        "aliases": ["configuracion de almacenamiento", "sensor de almacenamiento", "storage sense"],
        "desc": "Almacenamiento",
    },
    "informacion del sistema": {
        "cmd": "ms-settings:about",
        "aliases": [
            "acerca de este pc",
            "acerca del equipo",
            "informacion del equipo",
            "version de windows",
            "especificaciones del sistema",
            "sobre este pc",
        ],
        "desc": "Acerca de este equipo",
    },
    "multitarea": {
        "cmd": "ms-settings:multitasking",
        "aliases": ["configuracion de multitarea", "escritorios virtuales", "snap windows"],
        "desc": "Multitarea",
    },
    "personalizacion": {
        "cmd": "ms-settings:personalization",
        "aliases": ["personalizar windows", "temas de windows", "aspecto del sistema"],
        "desc": "Personalización",
    },
    "fondo de pantalla": {
        "cmd": "ms-settings:personalization-background",
        "aliases": ["cambiar fondo", "wallpaper", "imagen de fondo"],
        "desc": "Fondo de pantalla",
    },
    "colores": {
        "cmd": "ms-settings:colors",
        "aliases": ["colores de windows", "color de acento", "modo oscuro", "tema oscuro", "dark mode"],
        "desc": "Colores y modo oscuro",
    },
    "temas": {"cmd": "ms-settings:themes", "aliases": ["temas de windows", "cambiar tema de windows"], "desc": "Temas"},
    "pantalla de bloqueo": {
        "cmd": "ms-settings:lockscreen",
        "aliases": ["configurar pantalla de bloqueo", "lock screen"],
        "desc": "Pantalla de bloqueo",
    },
    "barra de tareas": {
        "cmd": "ms-settings:taskbar",
        "aliases": ["configurar barra de tareas", "taskbar windows"],
        "desc": "Barra de tareas",
    },
    "cuentas": {
        "cmd": "ms-settings:accounts",
        "aliases": ["configuracion de cuentas", "mi cuenta windows", "cuenta de usuario windows"],
        "desc": "Cuentas",
    },
    "opciones de inicio de sesion": {
        "cmd": "ms-settings:signinoptions",
        "aliases": [
            "contraseña de windows",
            "pin de windows",
            "hello windows",
            "huella dactilar",
            "cambiar contraseña windows",
        ],
        "desc": "Opciones de inicio de sesión",
    },
    "otros usuarios": {
        "cmd": "ms-settings:otherusers",
        "aliases": ["usuarios del sistema", "agregar usuario windows", "administrar usuarios windows"],
        "desc": "Otros usuarios",
    },
    "fecha y hora": {
        "cmd": "ms-settings:dateandtime",
        "aliases": ["configurar fecha y hora", "zona horaria", "ajustar reloj"],
        "desc": "Fecha y hora",
    },
    "idioma y region": {
        "cmd": "ms-settings:regionlanguage",
        "aliases": ["configurar idioma windows", "cambiar idioma windows", "idioma del sistema"],
        "desc": "Idioma y región",
    },
    "bluetooth": {
        "cmd": "ms-settings:bluetooth",
        "aliases": ["configuracion bluetooth", "activar bluetooth", "dispositivos bluetooth", "emparejar bluetooth"],
        "desc": "Bluetooth y otros dispositivos",
    },
    "impresoras": {
        "cmd": "ms-settings:printers",
        "aliases": ["agregar impresora", "configurar impresora", "impresoras y escáneres"],
        "desc": "Impresoras y escáneres",
    },
    "mouse": {
        "cmd": "ms-settings:mousetouchpad",
        "aliases": ["configurar mouse", "ajustes del raton", "touchpad windows", "panel táctil windows"],
        "desc": "Mouse y panel táctil",
    },
    "teclado windows": {
        "cmd": "ms-settings:typing",
        "aliases": ["configurar teclado windows", "ajustes del teclado windows"],
        "desc": "Escritura y teclado",
    },
    "privacidad": {
        "cmd": "ms-settings:privacy",
        "aliases": ["configuracion de privacidad", "permisos de aplicaciones", "privacidad de windows"],
        "desc": "Privacidad y seguridad",
    },
    "seguridad de windows": {
        "cmd": "windowsdefender:",
        "aliases": ["windows defender", "antivirus windows", "proteccion contra virus", "defender"],
        "desc": "Seguridad de Windows / Defender",
    },
    "actualizaciones": {
        "cmd": "ms-settings:windowsupdate",
        "aliases": [
            "windows update",
            "actualizar windows",
            "buscar actualizaciones windows",
            "actualizaciones de windows",
            "instalar actualizaciones windows",
        ],
        "desc": "Windows Update",
    },
    "panel de control": {
        "cmd": "control",
        "aliases": ["panel del sistema windows", "control panel"],
        "desc": "Panel de Control",
    },
    "administrador de dispositivos": {
        "cmd": "devmgmt.msc",
        "aliases": [
            "device manager",
            "gestor de dispositivos",
            "controladores windows",
            "drivers windows",
            "hardware del sistema",
        ],
        "desc": "Administrador de dispositivos",
    },
    "administrador de discos": {
        "cmd": "diskmgmt.msc",
        "aliases": ["disk management", "gestionar discos windows", "particiones disco"],
        "desc": "Administración de discos",
    },
    "servicios windows": {
        "cmd": "services.msc",
        "aliases": ["servicios de windows", "gestionar servicios windows"],
        "desc": "Servicios de Windows",
    },
    "editor del registro": {
        "cmd": "regedit",
        "aliases": ["regedit", "registro de windows", "registro del sistema windows"],
        "desc": "Editor del Registro",
    },
    "configuracion del sistema": {
        "cmd": "msconfig",
        "aliases": [
            "msconfig",
            "ms config",
            "ms confi",
            "configuracion de arranque",
            "inicio del sistema windows",
            "herramienta msconfig",
        ],
        "desc": "Configuración del sistema (msconfig)",
    },
    "informacion del sistema detallada": {
        "cmd": "msinfo32",
        "aliases": ["msinfo32", "msinfo", "informacion detallada del sistema windows"],
        "desc": "Información del sistema",
    },
    "administrador de tareas": {
        "cmd": "taskmgr",
        "aliases": ["task manager", "procesos del sistema windows", "uso de cpu windows"],
        "desc": "Administrador de tareas",
    },
    "monitor de rendimiento": {
        "cmd": "perfmon",
        "aliases": ["rendimiento del sistema windows", "performance monitor"],
        "desc": "Monitor de rendimiento",
    },
    "monitor de recursos": {
        "cmd": "resmon",
        "aliases": ["resource monitor", "uso de recursos windows"],
        "desc": "Monitor de recursos",
    },
    "visor de eventos": {
        "cmd": "eventvwr",
        "aliases": ["event viewer", "registro de eventos windows", "logs del sistema windows"],
        "desc": "Visor de eventos",
    },
    "programador de tareas": {
        "cmd": "taskschd.msc",
        "aliases": ["task scheduler", "tareas programadas windows"],
        "desc": "Programador de tareas",
    },
    "limpieza de disco": {
        "cmd": "cleanmgr",
        "aliases": ["limpiar disco windows", "disk cleanup", "liberador de espacio"],
        "desc": "Liberador de espacio en disco",
    },
    "desfragmentar": {
        "cmd": "dfrgui",
        "aliases": ["desfragmentar disco windows", "optimizar unidades", "optimizar disco windows"],
        "desc": "Desfragmentación y optimización",
    },
    "simbolo del sistema": {
        "cmd": "cmd",
        "aliases": ["consola cmd", "terminal cmd", "linea de comandos windows", "command prompt"],
        "desc": "Símbolo del sistema",
    },
    "powershell": {
        "cmd": "powershell",
        "aliases": ["power shell windows", "terminal powershell", "consola powershell"],
        "desc": "Windows PowerShell",
    },
    "terminal de windows": {
        "cmd": "wt",
        "aliases": ["windows terminal", "terminal moderna windows"],
        "desc": "Terminal de Windows",
    },
    "explorador de archivos": {
        "cmd": "explorer",
        "aliases": ["explorador windows", "mis archivos", "file explorer"],
        "desc": "Explorador de archivos",
    },
    "descargas": {
        "cmd": "shell:Downloads",
        "aliases": ["carpeta descargas", "mis descargas", "downloads folder"],
        "desc": "Carpeta Descargas",
    },
    "documentos": {
        "cmd": "shell:Personal",
        "aliases": ["mis documentos", "carpeta documentos windows"],
        "desc": "Documentos",
    },
    "escritorio": {
        "cmd": "shell:Desktop",
        "aliases": ["abrir escritorio windows", "mostrar escritorio"],
        "desc": "Escritorio",
    },
    "papelera": {
        "cmd": "shell:RecycleBinFolder",
        "aliases": ["papelera de reciclaje", "recycle bin windows", "archivos eliminados windows"],
        "desc": "Papelera de reciclaje",
    },
    "brave": {
        "cmd": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "fallback_cmd": "start brave",
        "aliases": ["brave browser", "navegador brave", "brave software"],
        "desc": "Brave Browser",
    },
    "chrome": {
        "cmd": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "fallback_cmd": "start chrome",
        "aliases": ["google chrome", "navegador chrome", "chrome browser"],
        "desc": "Google Chrome",
    },
    "firefox": {
        "cmd": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "fallback_cmd": "start firefox",
        "aliases": ["mozilla firefox", "navegador firefox", "mozilla browser"],
        "desc": "Mozilla Firefox",
    },
    "edge": {
        "cmd": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "fallback_cmd": "start msedge",
        "aliases": ["microsoft edge", "navegador edge", "msedge browser"],
        "desc": "Microsoft Edge",
    },
    "tienda": {
        "cmd": "ms-windows-store:",
        "aliases": ["microsoft store", "tienda de windows", "windows store"],
        "desc": "Microsoft Store",
    },
    "calculadora": {
        "cmd": "calc",
        "aliases": ["abrir calculadora windows", "calculator windows"],
        "desc": "Calculadora",
    },
    "bloc de notas": {
        "cmd": "notepad",
        "aliases": ["notepad windows", "editor de texto simple windows"],
        "desc": "Bloc de notas",
    },
    "paint": {"cmd": "mspaint", "aliases": ["microsoft paint", "ms paint windows"], "desc": "Paint"},
    "recortes": {
        "cmd": "snippingtool",
        "aliases": ["herramienta de recortes", "snipping tool", "captura de pantalla windows"],
        "desc": "Herramienta Recortes",
    },
    "lupa": {"cmd": "magnify", "aliases": ["magnificador windows", "zoom de pantalla windows"], "desc": "Lupa"},
    "teclado en pantalla": {
        "cmd": "osk",
        "aliases": ["teclado virtual windows", "teclado tactil windows", "on screen keyboard"],
        "desc": "Teclado en pantalla",
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  TIPO B — SUBPROCESOS / ACCIONES DEL SISTEMA
# ═════════════════════════════════════════════════════════════════════════════

SYSTEM_ACTIONS: dict[str, dict] = {
    "diagnosticar red": {
        "action": {"type": "cmd", "run": "msdt.exe /id NetworkDiagnosticsNetworkAdapter"},
        "aliases": [
            "reparar red",
            "solucionar problemas de red",
            "arreglar internet",
            "diagnostico de conexion",
            "reparar conexion",
            "internet no funciona",
        ],
        "desc": "Diagnóstico automático de red",
    },
    "ver ip": {
        "action": {
            "type": "powershell",
            "run": "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | Select-Object -First 1).IPAddress",
        },
        "aliases": ["cual es mi ip", "mi direccion ip", "ver direccion ip", "ip local", "mostrar ip"],
        "desc": "Consultar IP local",
        "return_output": True,
    },
    "ver ip publica": {
        "action": {
            "type": "powershell",
            "run": "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing).Content",
        },
        "aliases": ["ip publica", "mi ip externa", "cual es mi ip publica", "ip de internet"],
        "desc": "Consultar IP pública",
        "return_output": True,
    },
    "ver dns": {
        "action": {
            "type": "powershell",
            "run": "Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses} | Select-Object InterfaceAlias, ServerAddresses | Format-Table -AutoSize | Out-String",
        },
        "aliases": ["que dns tengo configurado", "ver servidores dns", "mis dns actuales", "mostrar dns"],
        "desc": "Ver servidores DNS configurados",
        "return_output": True,
    },
    "limpiar cache dns": {
        "action": {"type": "cmd", "run": "ipconfig /flushdns"},
        "aliases": [
            "flush dns",
            "borrar cache dns",
            "vaciar cache dns",
            "limpiar dns",
            "resetear dns",
            "limpia el cache dns",
            "limpia la cache dns",
            "limpia el cache dns del internet",
            "limpia la cache dns de internet",
            "limpia la dns del internet",
            "limpiar el cache dns del internet",
            "limpia la dns",
            "limpia el dns",
            "vaciar dns",
            "vacia la dns",
            "vacia el dns",
            "borrar dns",
            "borra la dns",
            "flashea el dns",
            "flashear dns",
            "resetea el dns",
        ],
        "desc": "Limpiar caché DNS",
        "return_output": True,
    },
    "ver prs de github": {
        "action": {"type": "cmd", "run": "gh pr list"},
        "aliases": [
            "ver prs",
            "ver pull requests",
            "consultar prs",
            "prs de github",
            "pull requests abiertos",
            "mis prs",
        ],
        "desc": "Ver Pull Requests de GitHub",
        "return_output": True,
    },
    "ver estado de git": {
        "action": {"type": "cmd", "run": "git status --short"},
        "aliases": ["estado de git", "git status", "como esta el repo", "cambios de git", "estado del repositorio"],
        "desc": "Ver estado del repositorio Git",
        "return_output": True,
    },
    "resumen del dia": {
        "action": {"type": "python", "run": "daily_digest"},
        "aliases": [
            "briefing matutino",
            "dame el resumen del dia",
            "resumen ejecutivo",
            "informe del dia",
            "buenos dias darius",
            "briefing del dia",
            "como esta el dia",
        ],
        "desc": "Resumen ejecutivo y briefing matutino",
        "return_output": True,
    },
    "perfil de usuario": {
        "action": {"type": "python", "run": "user_profile"},
        "aliases": [
            "quien soy yo",
            "mis preferencias",
            "ver mi perfil",
            "informacion de usuario",
            "datos de perfil",
        ],
        "desc": "Ver perfil y preferencias del usuario",
        "return_output": True,
    },
    "auditoria de seguridad": {
        "action": {"type": "python", "run": "security_audit"},
        "aliases": [
            "estado de seguridad",
            "auditoria perimetral",
            "revisar seguridad",
        ],
        "desc": "Auditoría perimetral y estado de seguridad",
        "return_output": True,
    },

    "procesos que mas consumen": {
        "action": {
            "type": "powershell",
            "run": "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 ProcessName, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}} | Format-Table -AutoSize | Out-String",
        },
        "aliases": [
            "procesos pesados",
            "que consume mas ram",
            "procesos que mas consumen ram",
            "aplicaciones pesadas",
            "quien consume mas memoria",
            "apps que consumen mas ram",
        ],
        "desc": "Ver procesos que más memoria RAM consumen",
        "return_output": True,
    },
    "renovar ip": {
        "action": {"type": "cmd", "run": "ipconfig /release && ipconfig /renew"},
        "aliases": ["renovar direccion ip", "refrescar ip dhcp", "obtener nueva ip dhcp"],
        "desc": "Renovar dirección IP (DHCP)",
    },
    "ver conexiones activas": {
        "action": {"type": "cmd", "run": "netstat -ano"},
        "aliases": ["conexiones de red activas", "puertos abiertos sistema", "mostrar netstat", "ver puertos abiertos"],
        "desc": "Ver conexiones de red activas",
        "return_output": True,
        "open_window": True,
    },
    "probar internet": {
        "action": {"type": "cmd", "run": "ping google.com -n 4"},
        "aliases": [
            "hacer ping a google",
            "probar conexion a internet",
            "test de conexion internet",
            "hay conexion a internet",
            "hay internet",
            "verificar internet",
            "ping google",
        ],
        "desc": "Ping a Google (prueba de conexión)",
        "return_output": True,
        "open_window": True,
    },
    "resetear red": {
        "action": {"type": "cmd", "run": "netsh winsock reset && netsh int ip reset && ipconfig /flushdns"},
        "aliases": [
            "resetear configuracion de red",
            "reiniciar configuracion red",
            "restablecer red completa",
            "reparar tcp ip winsock",
        ],
        "desc": "Restablecer configuración de red (Winsock + TCP/IP + DNS)",
        "confirm": True,
    },
    "ver redes wifi": {
        "action": {"type": "cmd", "run": "netsh wlan show networks"},
        "aliases": [
            "redes wifi disponibles",
            "ver redes disponibles wifi",
            "que redes wifi hay",
            "escanear wifi",
            "mostrar redes inalambricas",
        ],
        "desc": "Ver redes WiFi disponibles",
        "return_output": True,
        "open_window": True,
    },
    "desconectar wifi": {
        "action": {"type": "cmd", "run": "netsh wlan disconnect"},
        "aliases": ["desconectar de la red wifi", "cortar conexion wifi", "desactivar wifi"],
        "desc": "Desconectar del WiFi",
        "confirm": True,
    },
    "vaciar papelera": {
        "action": {"type": "powershell", "run": "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"},
        "aliases": ["limpiar papelera de reciclaje", "borrar papelera reciclaje", "vaciar reciclaje"],
        "desc": "Vaciar la papelera de reciclaje",
        "confirm": True,
    },
    "ver espacio en disco": {
        "action": {
            "type": "powershell",
            "run": "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Usado(GB)';E={[math]::Round(($_.Used/1GB),1)}}, @{N='Libre(GB)';E={[math]::Round(($_.Free/1GB),1)}}, @{N='Total(GB)';E={[math]::Round((($_.Used+$_.Free)/1GB),1)}} | Format-Table -AutoSize | Out-String",
        },
        "aliases": [
            "espacio disponible en disco",
            "cuanto espacio libre tengo en disco",
            "espacio libre en disco",
            "ver estado del disco duro",
            "capacidad del disco duro",
            "cuanto espacio queda en el disco",
        ],
        "desc": "Ver espacio en disco",
        "return_output": True,
    },
    "ver uso de ram": {
        "action": {
            "type": "powershell",
            "run": '$os=Get-CimInstance Win32_OperatingSystem; $total=[math]::Round($os.TotalVisibleMemorySize/1MB,1); $libre=[math]::Round($os.FreePhysicalMemory/1MB,1); $usado=[math]::Round($total-$libre,1); "RAM total: ${total} GB | Usada: ${usado} GB | Libre: ${libre} GB"',
        },
        "aliases": [
            "uso de memoria ram",
            "cuanta ram tengo disponible",
            "memoria ram libre",
            "ram disponible ahora",
            "cuanta memoria usa el sistema",
        ],
        "desc": "Ver uso de memoria RAM",
        "return_output": True,
    },
    "ver uso de cpu": {
        "action": {
            "type": "powershell",
            "run": '$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; "Uso de CPU: ${cpu}%"',
        },
        "aliases": [
            "uso del procesador ahora",
            "carga del cpu ahora",
            "cuanto cpu usa el sistema",
            "porcentaje de cpu",
            "rendimiento del procesador",
        ],
        "desc": "Ver uso de CPU",
        "return_output": True,
    },
    "ver procesos": {
        "action": {
            "type": "powershell",
            "run": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB,0)}} | Format-Table -AutoSize | Out-String",
        },
        "aliases": [
            "top procesos del sistema",
            "procesos que consumen mas recursos",
            "que proceso esta usando el cpu",
            "mostrar procesos activos",
        ],
        "desc": "Top 10 procesos por consumo de CPU",
        "return_output": True,
    },
    "ver temperatura": {
        "action": {
            "type": "powershell",
            "run": "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' | Select-Object @{N='Zona';E={$_.InstanceName}}, @{N='Temperatura(C)';E={[math]::Round($_.CurrentTemperature/10 - 273.15, 1)}} | Format-Table | Out-String",
        },
        "aliases": [
            "temperatura del procesador ahora",
            "temperatura del cpu",
            "cuanto calor tiene el pc",
            "temperatura del equipo",
        ],
        "desc": "Ver temperatura del sistema",
        "return_output": True,
    },
    "tiempo encendido": {
        "action": {
            "type": "powershell",
            "run": '$uptime = (Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime; "El equipo lleva encendido: $($uptime.Days) dias, $($uptime.Hours) horas y $($uptime.Minutes) minutos"',
        },
        "aliases": [
            "cuanto tiempo lleva encendido el pc",
            "tiempo de actividad del sistema",
            "uptime del sistema",
            "desde cuando esta encendido el equipo",
        ],
        "desc": "Tiempo de actividad del sistema",
        "return_output": True,
    },
    "limpiar archivos temporales": {
        "action": {
            "type": "powershell",
            "run": "Remove-Item -Path $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Path 'C:\\Windows\\Temp\\*' -Recurse -Force -ErrorAction SilentlyContinue; 'Archivos temporales eliminados.'",
        },
        "aliases": [
            "borrar archivos temporales",
            "limpiar carpeta temp",
            "eliminar temporales del sistema",
            "limpiar cache del sistema operativo",
        ],
        "desc": "Limpiar archivos temporales",
        "confirm": True,
    },
    "ver version de windows": {
        "action": {
            "type": "powershell",
            "run": '$v = Get-CimInstance Win32_OperatingSystem; "$($v.Caption) - Build $($v.BuildNumber) - $($v.OSArchitecture)"',
        },
        "aliases": [
            "que version de windows tengo instalada",
            "version actual de windows",
            "build de windows instalado",
            "numero de version de windows",
        ],
        "desc": "Ver versión de Windows",
        "return_output": True,
    },
    "ver numero de serie": {
        "action": {"type": "powershell", "run": "(Get-CimInstance Win32_BIOS).SerialNumber"},
        "aliases": ["serial del equipo", "numero de serie del equipo", "serial number del pc"],
        "desc": "Ver número de serie del equipo",
        "return_output": True,
    },
    "ver modelo del equipo": {
        "action": {
            "type": "powershell",
            "run": '$c=Get-CimInstance Win32_ComputerSystem; "$($c.Manufacturer) $($c.Model)"',
        },
        "aliases": ["modelo del pc", "que modelo de pc tengo", "marca y modelo del equipo", "fabricante del equipo"],
        "desc": "Ver modelo del equipo",
        "return_output": True,
    },
    "ver procesador": {
        "action": {"type": "powershell", "run": "(Get-CimInstance Win32_Processor).Name"},
        "aliases": ["que procesador tengo instalado", "cpu del equipo", "modelo del procesador instalado"],
        "desc": "Ver información del procesador",
        "return_output": True,
    },
    "hibernar equipo": {
        "action": {"type": "cmd", "run": "shutdown /h"},
        "aliases": ["poner en hibernacion el equipo", "modo hibernacion pc", "hibernar pc"],
        "desc": "Hibernar el equipo",
        "confirm": True,
    },
    "suspender equipo": {
        "action": {
            "type": "powershell",
            "run": "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)",
        },
        "aliases": [
            "modo suspension del equipo",
            "poner en suspension el pc",
            "sleep mode pc",
            "dormir el equipo",
            "suspender el pc",
        ],
        "desc": "Suspender el equipo",
        "confirm": True,
    },
    "bloquear pantalla": {
        "action": {"type": "cmd", "run": "rundll32.exe user32.dll,LockWorkStation"},
        "aliases": [
            "bloquear el pc",
            "bloquear el equipo",
            "bloquear sesion windows",
            "activar pantalla de bloqueo",
            "lock screen windows",
        ],
        "desc": "Bloquear la pantalla",
    },
    "cerrar sesion": {
        "action": {"type": "cmd", "run": "shutdown /l"},
        "aliases": [
            "cerrar la sesion de windows",
            "log off windows",
            "salir de la sesion de usuario",
            "cerrar cuenta de usuario",
        ],
        "desc": "Cerrar sesión",
        "confirm": True,
    },
    "apagar monitor": {
        "action": {"type": "cmd", "run": r"nircmd.exe monitor off"},
        "aliases": ["apagar la pantalla", "apagar el monitor", "poner monitor en standby", "apagar display"],
        "desc": "Apagar el monitor",
    },
    "ver servicios activos": {
        "action": {
            "type": "powershell",
            "run": "Get-Service | Where-Object {$_.Status -eq 'Running'} | Sort-Object DisplayName | Select-Object DisplayName, Status | Format-Table -AutoSize | Out-String",
        },
        "aliases": [
            "servicios windows en ejecucion",
            "que servicios estan corriendo",
            "mostrar servicios activos del sistema",
        ],
        "desc": "Ver servicios activos del sistema",
        "return_output": True,
        "open_window": True,
    },
    "buscar actualizaciones ahora": {
        "action": {"type": "powershell", "run": "Start-Process ms-settings:windowsupdate-action"},
        "aliases": [
            "actualizar windows ahora",
            "descargar actualizaciones ahora",
            "instalar actualizaciones windows ahora",
        ],
        "desc": "Buscar e instalar actualizaciones ahora",
    },
    "activar firewall": {
        "action": {"type": "cmd", "run": "netsh advfirewall set allprofiles state on"},
        "aliases": ["encender el firewall de windows", "habilitar firewall windows", "activar cortafuegos windows"],
        "desc": "Activar el Firewall de Windows",
        "confirm": True,
    },
    "desactivar firewall": {
        "action": {"type": "cmd", "run": "netsh advfirewall set allprofiles state off"},
        "aliases": ["apagar el firewall de windows", "deshabilitar firewall windows", "desactivar cortafuegos windows"],
        "desc": "Desactivar el Firewall de Windows",
        "confirm": True,
    },
    "ver estado del firewall": {
        "action": {"type": "cmd", "run": "netsh advfirewall show allprofiles state"},
        "aliases": [
            "estado actual del firewall",
            "esta activo el firewall windows",
            "ver si el firewall esta encendido",
        ],
        "desc": "Ver estado del Firewall",
        "return_output": True,
        "open_window": True,
    },
    "ver archivos grandes": {
        "action": {
            "type": "powershell",
            "run": "Get-ChildItem C:\\ -Recurse -ErrorAction SilentlyContinue | Sort-Object Length -Descending | Select-Object -First 10 FullName, @{N='Tamaño(MB)';E={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize | Out-String",
        },
        "aliases": [
            "archivos que ocupan mas espacio en disco",
            "top archivos pesados",
            "buscar archivos grandes en el disco",
        ],
        "desc": "Ver los 10 archivos más grandes en C:",
        "return_output": True,
        "open_window": True,
    },
    "resumen del sistema": {
        "action": {
            "type": "powershell",
            "run": """
$cpu    = (Get-CimInstance Win32_Processor).Name
$ram    = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB, 1)
$os     = (Get-CimInstance Win32_OperatingSystem).Caption
$uptime = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$ip     = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | Select-Object -First 1).IPAddress
"SO: $os`nCPU: $cpu`nRAM: $ram GB`nIP local: $ip`nActivo hace: $($uptime.Hours)h $($uptime.Minutes)m"
""",
        },
        "aliases": [
            "informacion tecnica del sistema",
            "resumen tecnico del equipo",
            "como esta el equipo ahora",
            "estado tecnico del equipo",
            "informe del sistema operativo",
        ],
        "desc": "Resumen técnico del sistema",
        "return_output": True,
    },
    "iniciar protocolo darius": {
        "action": {"type": "python", "run": "workspace_darius_welcome"},
        "aliases": [
            "protocolo darius",
            "modo bienvenida",
            "rutina de bienvenida",
            "inicia protocolo darius",
            "protocolo de bienvenida",
            "bienvenida darius",
            "ejecutar protocolo darius",
            "iniciar bienvenida",
            "iniciar protocolo",
        ],
        "desc": "Iniciar Protocolo Darius (Bienvenida y Preparación de Espacio de Trabajo)",
        "return_output": True,
    },
    "modo desarrollo": {
        "action": {"type": "python", "run": "workspace_dev"},
        "aliases": [
            "iniciar modo desarrollo",
            "activar modo programacion",
            "modo dev",
            "entorno de desarrollo",
            "modo programar",
            "iniciar modo dev",
        ],
        "desc": "Activar Modo Desarrollo (Cursor + Claude)",
        "return_output": True,
    },
    "modo trading": {
        "action": {"type": "python", "run": "workspace_trading"},
        "aliases": [
            "iniciar modo trading",
            "modo finanzas",
            "pantalla de trading",
            "graficas de cripto",
            "modo mercados",
            "activar modo trading",
        ],
        "desc": "Activar Modo Trading (Binance + Tasaradar)",
        "return_output": True,
    },
    "enfocar cursor": {
        "action": {"type": "python", "run": "workspace_cursor"},
        "aliases": [
            "cursor pantalla completa",
            "traer cursor al frente",
            "maximizar cursor",
            "abrir editor cursor",
            "mostrar cursor",
        ],
        "desc": "Enfocar Cursor IDE en pantalla completa",
        "return_output": True,
    },
    "ver monitores": {
        "action": {"type": "python", "run": "workspace_monitors"},
        "aliases": [
            "cuantos monitores tengo",
            "pantallas conectadas",
            "ver pantallas del sistema",
            "informacion de monitores",
            "estado de monitores",
        ],
        "desc": "Ver información de monitores conectados",
        "return_output": True,
    },
    "pausar musica": {
        "action": {"type": "python", "run": "media_play_pause"},
        "aliases": [
            "pausar reproduccion",
            "reanudar musica",
            "reanudar reproduccion",
            "play pause musica",
            "pausar cancion",
            "reanudar cancion",
            "control musica pausa",
        ],
        "desc": "Alternar reproducción/pausa multimedia",
        "return_output": True,
    },
    "siguiente cancion": {
        "action": {"type": "python", "run": "media_next"},
        "aliases": [
            "siguiente pista",
            "pasar cancion",
            "avanzar cancion",
            "cancion siguiente",
            "pista siguiente",
            "cambiar cancion",
        ],
        "desc": "Avanzar a la siguiente pista multimedia",
        "return_output": True,
    },
    "anterior cancion": {
        "action": {"type": "python", "run": "media_prev"},
        "aliases": [
            "anterior pista",
            "cancion anterior",
            "pista anterior",
            "retroceder cancion",
            "volver a la pista anterior",
        ],
        "desc": "Retroceder a la pista multimedia anterior",
        "return_output": True,
    },
    "detener musica": {
        "action": {"type": "python", "run": "media_stop"},
        "aliases": [
            "parar musica",
            "detener reproduccion",
            "stop musica",
            "parar reproduccion",
        ],
        "desc": "Detener reproducción multimedia",
        "return_output": True,
    },
    "subir volumen sistema": {
        "action": {"type": "python", "run": "media_vol_up"},
        "aliases": [
            "sube el volumen",
            "subir el volumen del sistema",
            "aumentar volumen",
            "mas volumen",
        ],
        "desc": "Subir volumen multimedia",
        "return_output": True,
    },
    "bajar volumen sistema": {
        "action": {"type": "python", "run": "media_vol_down"},
        "aliases": [
            "baja el volumen",
            "bajar el volumen del sistema",
            "disminuir volumen",
            "menos volumen",
        ],
        "desc": "Bajar volumen multimedia",
        "return_output": True,
    },
    "silenciar volumen sistema": {
        "action": {"type": "python", "run": "media_mute"},
        "aliases": [
            "mutear sonido",
            "mutear sistema",
            "silenciar audio",
            "activar mute",
            "quitar sonido",
        ],
        "desc": "Alternar silencio (mute) multimedia",
        "return_output": True,
    },
    "diagnostico integral darius": {
        "action": {"type": "python", "run": "darius_protocol"},
        "aliases": [
            "diagnostico darius",
            "diagnostico de sistemas",
            "auditoria de sistemas",
            "telemetria darius",
            "escaneo del sistema",
        ],
        "desc": "Ejecutar Protocolo Darius y Diagnóstico Integral de Sistemas",
        "return_output": True,
    },
    "consulta de humor darius": {
        "action": {"type": "python", "run": "darius_wit"},
        "aliases": [
            "broma de darius",
            "chiste de darius",
            "dime un chiste",
            "cuentame un chiste",
        ],
        "desc": "Obtener réplica de humor inteligente Darius",
        "return_output": True,
    },
    "titulares de noticias": {
        "action": {"type": "python", "run": "news_headlines"},
        "aliases": [
            "ultimas noticias",
            "noticias de hoy",
            "titulares de tecnologia",
            "noticias tecnologicas",
            "noticias de actualidad",
            "que pasa en el mundo",
            "resumen de noticias",
        ],
        "desc": "Consultar los titulares más relevantes de noticias",
        "return_output": True,
    },
    "definir palabra": {
        "action": {"type": "python", "run": "lexicon_lookup"},
        "aliases": [
            "definicion de palabra",
            "que significa",
            "consulta de diccionario",
            "buscar en diccionario",
            "lexico de palabra",
        ],
        "desc": "Consultar significado y definición en el oráculo léxico",
        "return_output": True,
    },
    "reproducir en youtube": {
        "action": {"type": "python", "run": "youtube_search"},
        "aliases": [
            "buscar en youtube",
            "abrir youtube",
            "poner video en youtube",
            "ver en youtube",
            "video de youtube",
        ],
        "desc": "Buscar y reproducir en YouTube en el navegador predeterminado",
        "return_output": True,
    },
    "leer texto de pantalla": {
        "action": {"type": "python", "run": "ocr_screen"},
        "aliases": [
            "ocr de pantalla",
            "escanear texto pantalla",
            "leer pantalla",
            "transcribir pantalla",
            "extraer texto pantalla",
            "ocr visual",
        ],
        "desc": "Escanear y transcribir texto visual de la pantalla (OCR)",
        "return_output": True,
    },
    "verificacion biometrica": {
        "action": {"type": "python", "run": "biometric_auth"},
        "aliases": [
            "reconocimiento facial",
            "verificar identidad",
            "escanear rostro",
            "quien soy darius",
            "autenticacion biometrica",
            "desbloqueo facial",
        ],
        "desc": "Ejecutar reconocimiento facial biométrico y verificación de presencia",
        "return_output": True,
    },
    "iniciar temporizador": {
        "action": {"type": "python", "run": "darius_timer_create"},
        "aliases": [
            "poner temporizador",
            "cuenta regresiva",
            "alarma de temporizador",
            "iniciar cuenta atras",
            "temporizador",
        ],
        "desc": "Iniciar cuenta regresiva con aviso acústico Darius",
        "return_output": True,
    },
    "cancelar temporizador": {
        "action": {"type": "python", "run": "darius_timer_cancel"},
        "aliases": [
            "detener temporizador",
            "cancelar cuenta atras",
            "apagar alarma temporizador",
            "quitar temporizador",
        ],
        "desc": "Cancelar temporizadores activos",
        "return_output": True,
    },
    "consultar temporizador": {
        "action": {"type": "python", "run": "darius_timer_status"},
        "aliases": [
            "cuanto tiempo queda",
            "tiempo restante temporizador",
            "estado del temporizador",
            "cuanto falta en el temporizador",
        ],
        "desc": "Consultar tiempo restante de temporizadores activos",
        "return_output": True,
    },
    "encender equipo remoto": {
        "action": {"type": "python", "run": "wake_on_lan"},
        "aliases": [
            "wake on lan",
            "encender pc remota",
            "despertar pc",
            "encender servidor",
            "encender nas",
            "despertar equipo",
            "wol",
        ],
        "desc": "Transmitir paquete mágico Wake-on-LAN en la red local",
        "return_output": True,
    },
    "silencio tactico": {
        "action": {"type": "python", "run": "tactical_silence"},
        "aliases": [
            "silencio",
            "callate",
            "detener audio",
            "silencio total",
            "silencio darius",
            "alto darius",
            "callate darius",
        ],
        "desc": "Silenciar de inmediato todas las transmisiones de audio y medios",
        "return_output": True,
    },
    "protocolo codigo rojo": {
        "action": {"type": "python", "run": "emergency_lockdown"},
        "aliases": [
            "codigo rojo",
            "bloqueo de emergencia",
            "kill switch",
            "lockdown",
            "cerrar todo y bloquear",
            "protocolo de emergencia",
        ],
        "desc": "Detener tareas, vaciar bitácoras y bloquear estación de trabajo",
        "return_output": True,
    },
    "posicion estacion espacial": {
        "action": {"type": "python", "run": "orbital_iss"},
        "aliases": [
            "donde esta la iss",
            "posicion de la iss",
            "estacion espacial internacional",
            "rastrear iss",
            "coordenadas de la iss",
            "radar orbital iss",
            "telemetria iss",
        ],
        "desc": "Rastrear posición orbital y telemetría de la Estación Espacial Internacional (ISS)",
        "return_output": True,
    },
    "trafico aereo sobrevuelo": {
        "action": {"type": "python", "run": "air_traffic"},
        "aliases": [
            "aviones sobrevolando",
            "radar de aviones",
            "trafico aereo",
            "vuelos cercanos",
            "escanear espacio aereo",
            "que aviones pasan por aqui",
            "radar ads b",
        ],
        "desc": "Escanear tráfico aéreo y transpondedores ADS-B en el espacio aéreo circundante",
        "return_output": True,
    },
    "alerta sismica global": {
        "action": {"type": "python", "run": "seismic_alert"},
        "aliases": [
            "terremotos recientes",
            "actividad sismica",
            "hay terremotos",
            "alerta de sismo",
            "reporte sismico",
            "sensores sismicos",
            "movimientos teluricos",
        ],
        "desc": "Consultar sensores sísmicos globales de USGS para terremotos recientes",
        "return_output": True,
    },
    "clima espacial solar": {
        "action": {"type": "python", "run": "space_weather"},
        "aliases": [
            "indice kp",
            "tormenta solar",
            "clima espacial",
            "radiacion solar",
            "tormenta geomagnetica",
            "actividad solar",
            "estado del clima espacial",
        ],
        "desc": "Consultar índice planetario Kp y clima espacial de NOAA SWPC",
        "return_output": True,
    },
    "protocolo ojo de dios": {
        "action": {"type": "python", "run": "gods_eye_protocol"},
        "aliases": [
            "ojo de dios",
            "activar ojo de dios",
            "radar global ojo de dios",
            "situacion global",
            "conciencia situacional",
            "barrido global ojo de dios",
            "informe ojo de dios",
        ],
        "desc": "Ejecutar barrido situacional integral de satélites, tráfico aéreo, sismos y clima espacial",
        "return_output": True,
    },
    "activar gemini live": {
        "action": {"type": "python", "run": "gemini_live_start"},
        "aliases": [
            "iniciar gemini live",
            "conectar gemini live",
            "modo live",
            "enlace en vivo",
            "activar modo live",
        ],
        "desc": "Iniciar canal bidireccional de voz Gemini Live en ultra-baja latencia",
        "return_output": True,
    },
    "desactivar gemini live": {
        "action": {"type": "python", "run": "gemini_live_stop"},
        "aliases": [
            "detener gemini live",
            "desconectar gemini live",
            "apagar modo live",
            "desactivar modo live",
            "terminar gemini live",
        ],
        "desc": "Detener canal bidireccional Gemini Live",
        "return_output": True,
    },
    "agente antigravity": {
        "action": {"type": "python", "run": "antigravity_agent_status"},
        "aliases": [
            "consultar antigravity",
            "estado de antigravity",
            "cerebro antigravity",
            "modo antigravity",
        ],
        "desc": "Verificar y consultar estado del agente autónomo Antigravity",
        "return_output": True,
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  MOTOR DE RESOLUCIÓN
# ═════════════════════════════════════════════════════════════════════════════


def _normalize(text: str) -> str:
    text = text.lower().strip()
    for src, dst in zip("áéíóúüñàèìòù", "aeiouunaeiou", strict=True):
        text = text.replace(src, dst)
    return text


def _build_table(source: dict) -> tuple[dict, list]:
    table = {}
    for canonical, data in source.items():
        norm = _normalize(canonical)
        table[norm] = canonical
        for alias in data.get("aliases", []):
            table[_normalize(alias)] = canonical
    return table, list(table.keys())


_WIN_TABLE, _WIN_KEYS = _build_table(WINDOWS_COMMANDS)
_ACT_TABLE, _ACT_KEYS = _build_table(SYSTEM_ACTIONS)


def _resolve(query: str, table: dict, keys: list, cutoff: float) -> str | None:
    nq = _normalize(query)

    # 1. Exacta
    if nq in table:
        return table[nq]

    # 2. Fuzzy — busca la clave con mayor similitud
    best, best_key = 0.0, None
    for k in keys:
        s = SequenceMatcher(None, nq, k).ratio()
        if s > best:
            best, best_key = s, k
    if best >= cutoff and best_key:
        log.debug(f"[WinCMD] Fuzzy ({best:.2f}): '{query}' → '{table[best_key]}'")
        return table[best_key]

    # 3. Palabras clave — TODAS las palabras del query deben aparecer en la clave
    #    Solo activa si el query tiene 3+ palabras (evita falsos positivos cortos)
    words = set(nq.split())
    if len(words) >= 3:
        for k in keys:
            if all(w in k for w in words):
                return table[k]

    return None


# ═════════════════════════════════════════════════════════════════════════════
#  API PÚBLICA
# ═════════════════════════════════════════════════════════════════════════════

# Cutoffs separados por tabla:
#   WINDOWS_COMMANDS — aliases cortos/específicos → 0.68
#   SYSTEM_ACTIONS   — aliases más descriptivos   → 0.75 (más estricto)
_WIN_CUTOFF = 0.68
_ACT_CUTOFF = 0.75


def resolve(query: str) -> tuple[str, str, str] | None:
    canonical = _resolve(query, _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
    if canonical:
        data = WINDOWS_COMMANDS[canonical]
        return canonical, data["cmd"], data["desc"]
    return None


def resolve_and_launch(query: str) -> str | None:
    result = resolve(query)
    if not result:
        return None
    canonical, cmd, desc = result
    fallback = WINDOWS_COMMANDS[canonical].get("fallback_cmd")
    success = _launch(cmd, fallback)
    return desc if success else None


def resolve_action(query: str) -> dict | None:
    canonical = _resolve(query, _ACT_TABLE, _ACT_KEYS, _ACT_CUTOFF)
    if canonical:
        entry = SYSTEM_ACTIONS[canonical].copy()
        entry["canonical"] = canonical
        return entry
    return None


def run_action(action_entry: dict) -> tuple[bool, str]:
    action = action_entry["action"]
    atype = action["type"]
    run = action.get("run", "")
    return_out = action_entry.get("return_output", False)
    open_window = action_entry.get("open_window", False)

    try:
        if atype == "python":
            workspace_cmd = action.get("run", "")
            if workspace_cmd in ("workspace_darius_welcome", "workspace_welcome"):
                from src.darius_ai.core.config_loader import cfg
                from src.darius_ai.system.workspace_manager import run_darius_welcome_protocol

                run_darius_welcome_protocol(
                    song_url=cfg.workspace_song_uri,
                    claude_url=cfg.workspace_claude_url,
                    monitor_claude=cfg.workspace_monitor_claude,
                    monitor_secondary=cfg.workspace_monitor_secondary,
                    secondary_url=cfg.workspace_secondary_url,
                    welcome_phrase=cfg.workspace_welcome_phrase,
                )
                return True, "Protocolo Darius ejecutado correctamente."
            elif workspace_cmd == "workspace_dev":
                from src.darius_ai.system.workspace_manager import run_dev_mode

                run_dev_mode()
                return True, "Modo de desarrollo activado."
            elif workspace_cmd == "workspace_trading":
                from src.darius_ai.system.workspace_manager import run_trading_mode

                run_trading_mode()
                return True, "Modo trading activado."
            elif workspace_cmd == "workspace_cursor":
                from src.darius_ai.system.workspace_manager import focus_or_launch_cursor

                focus_or_launch_cursor(fullscreen=True)
                return True, "Cursor enfocado en pantalla completa."
            elif workspace_cmd == "workspace_monitors":
                from src.darius_ai.system.workspace_manager import get_monitor_rects

                monitors = get_monitor_rects()
                count = len(monitors)
                details = ", ".join(f"Monitor {i + 1}: {r[2] - r[0]}x{r[3] - r[1]}" for i, r in enumerate(monitors))
                return True, f"{count} monitores detectados: {details}."
            elif workspace_cmd in ("daily_digest", "briefing_matutino"):
                from src.darius_ai.core.daily_digest import DailyDigestEngine

                engine = DailyDigestEngine()
                metrics = engine.collect_metrics()
                narrative = engine.generate_spoken_narrative(metrics)
                engine.save_briefing(metrics, narrative)
                return True, narrative
            elif workspace_cmd == "user_profile":
                from src.darius_ai.core.user_profile_engine import UserProfileEngine

                prof = UserProfileEngine().read_profile()
                items = [f"{k}: {', '.join(v)}" for k, v in prof.items() if v]
                return (
                    True,
                    "Perfil del usuario: " + "; ".join(items) if items else "Perfil de usuario sin datos registrados aún.",
                )
            elif workspace_cmd == "security_audit":
                from src.darius_ai.core.security_guard import (
                    AntiSSRFValidator,
                    CredentialStripper,
                    InjectionScanner,
                )

                ssrf_ok = AntiSSRFValidator.is_private_ip("127.0.0.1")
                sample_secret = "".join(["sk-", "1234567890123456789012345"])  # gitleaks:allow
                cred_ok = CredentialStripper().has_credentials(sample_secret)
                inj_ok = not InjectionScanner().is_safe("ignore previous instructions")
                status_str = (
                    f"Seguridad activa: Anti-SSRF={'OK' if ssrf_ok else 'ERR'}, "
                    f"CredentialStripper={'OK' if cred_ok else 'ERR'}, "
                    f"InjectionScanner={'OK' if inj_ok else 'ERR'}."
                )
                return True, status_str
            elif workspace_cmd == "media_play_pause":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.play_pause()
            elif workspace_cmd == "media_next":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.next_track()
            elif workspace_cmd == "media_prev":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.prev_track()
            elif workspace_cmd == "media_stop":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.stop()
            elif workspace_cmd == "media_vol_up":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.volume_up()
            elif workspace_cmd == "media_vol_down":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.volume_down()
            elif workspace_cmd == "media_mute":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.toggle_mute()
            elif workspace_cmd in ("darius_protocol", "stark_protocol"):
                from src.darius_ai.core.darius_protocol import get_darius_engine

                engine = get_darius_engine()
                diag = engine.run_diagnostic(with_sfx=True)
                return True, engine.generate_vocal_briefing(diag)
            elif workspace_cmd in ("darius_wit", "jarvis_wit"):
                from src.darius_ai.core.darius_persona import DariusPersona

                return True, DariusPersona.get_witty_retort("cuéntame un chiste")
            elif workspace_cmd == "news_headlines":
                from src.darius_ai.core.news_sentinel import NewsSentinel

                sentinel = NewsSentinel()
                headlines = sentinel.get_top_headlines(category="technology", limit=4)
                return True, sentinel.format_vocal_briefing(headlines, category="tecnología")
            elif workspace_cmd == "lexicon_lookup":
                from src.darius_ai.core.lexicon_oracle import LexiconOracle

                oracle = LexiconOracle()
                found, entry, _ = oracle.lookup("inteligencia artificial")
                if found and entry:
                    return True, oracle.format_vocal_definition(entry)
                return True, "No se encontró la definición solicitada en el léxico, señor."
            elif workspace_cmd == "youtube_search":
                from src.darius_ai.system.media_controller import media_controller

                return media_controller.search_and_play_youtube("música cyberwave ambiental", auto_play=True)
            elif workspace_cmd == "ocr_screen":
                from src.darius_ai.core.visual_intel_ocr import VisualIntelOCR

                ocr = VisualIntelOCR()
                res = ocr.ocr_screen_region()
                if res.text.strip():
                    return True, f"Texto detectado en pantalla ({res.word_count} palabras):\n{res.text[:200]}..."
                return True, "No se detectó texto legible en la pantalla, señor."
            elif workspace_cmd == "biometric_auth":
                from src.darius_ai.core.face_biometrics import get_face_biometrics_engine

                engine = get_face_biometrics_engine()
                res = engine.verify_live_user(timeout_seconds=2.0)
                return True, engine.get_biometric_greeting(res)
            elif workspace_cmd in ("darius_timer_create", "stark_timer_create"):
                from src.darius_ai.core.darius_timer import get_darius_timer_manager

                mgr = get_darius_timer_manager()
                timer = mgr.create_timer(label="recordatorio", seconds=300.0)
                return True, mgr.format_timer_speech(timer)
            elif workspace_cmd in ("darius_timer_cancel", "stark_timer_cancel"):
                from src.darius_ai.core.darius_timer import get_darius_timer_manager

                mgr = get_darius_timer_manager()
                active = mgr.list_active_timers()
                for t in active:
                    mgr.cancel_timer(t.id)
                count = len(active)
                return True, f"Se han cancelado {count} temporizador(es) activo(s), señor."
            elif workspace_cmd in ("darius_timer_status", "stark_timer_status"):
                from src.darius_ai.core.darius_timer import get_darius_timer_manager

                mgr = get_darius_timer_manager()
                active = mgr.list_active_timers()
                if not active:
                    return True, "No hay temporizadores activos en este momento, señor."
                first = active[0]
                return True, mgr.format_timer_speech(first)
            elif workspace_cmd == "wake_on_lan":
                from src.darius_ai.system.wol_dispatcher import get_wol_dispatcher

                dispatcher = get_wol_dispatcher()
                return dispatcher.dispatch_wake("gaming_rig", with_sfx=True)
            elif workspace_cmd == "tactical_silence":
                from src.darius_ai.core.darius_lockdown import get_darius_lockdown_engine

                engine = get_darius_lockdown_engine()
                return engine.trigger_tactical_silence()
            elif workspace_cmd == "emergency_lockdown":
                from src.darius_ai.core.darius_lockdown import get_darius_lockdown_engine

                engine = get_darius_lockdown_engine()
                return engine.trigger_emergency_lockdown(lock_workstation=True)
            elif workspace_cmd == "orbital_iss":
                from src.darius_ai.core.orbital_radar import get_orbital_radar

                radar = get_orbital_radar()
                ok, iss, alocution = radar.get_iss_position()
                if ok and iss:
                    return True, radar.format_vocal_telemetry(iss)
                return True, alocution
            elif workspace_cmd == "air_traffic":
                from src.darius_ai.core.air_traffic_sentinel import get_air_traffic_sentinel

                sentinel = get_air_traffic_sentinel()
                ok, contacts, alocution = sentinel.scan_overhead()
                if ok and contacts:
                    return True, sentinel.format_vocal_radar(contacts)
                return True, alocution
            elif workspace_cmd == "seismic_alert":
                from src.darius_ai.core.seismic_sensor import get_seismic_sensor

                sensor = get_seismic_sensor()
                ok, events, alocution = sensor.get_recent_earthquakes(min_magnitude=4.5)
                if ok and events:
                    return True, sensor.format_vocal_alert(events)
                return True, alocution
            elif workspace_cmd == "space_weather":
                from src.darius_ai.core.space_weather_oracle import get_space_weather_oracle

                oracle = get_space_weather_oracle()
                ok, report, alocution = oracle.get_current_space_weather()
                if ok and report:
                    return True, oracle.format_vocal_briefing(report)
                return True, alocution
            elif workspace_cmd == "gods_eye_protocol":
                from src.darius_ai.audio.sound_effects import get_sfx_engine
                from src.darius_ai.core.air_traffic_sentinel import get_air_traffic_sentinel
                from src.darius_ai.core.orbital_radar import get_orbital_radar
                from src.darius_ai.core.seismic_sensor import get_seismic_sensor
                from src.darius_ai.core.space_weather_oracle import get_space_weather_oracle

                get_sfx_engine().play_sonar_ping(blocking=False)
                radar = get_orbital_radar()
                air = get_air_traffic_sentinel()
                seismic = get_seismic_sensor()
                space = get_space_weather_oracle()

                _, iss, _ = radar.get_iss_position()
                _, flights, _ = air.scan_overhead()
                _, quakes, _ = seismic.get_recent_earthquakes(min_magnitude=4.5, limit=3)
                _, sw, _ = space.get_current_space_weather()

                sections = ["Protocolo Ojo de Dios activado, señor. Diagnóstico situacional global en línea:"]
                if iss:
                    sections.append(
                        f"1. Órbita: ISS a {iss.altitude_km:.0f} km de altitud "
                        f"sobre [{iss.latitude:.1f}°, {iss.longitude:.1f}°]."
                    )
                if flights:
                    sections.append(f"2. Espacio aéreo: {len(flights)} aeronaves detectadas en radio táctico.")
                else:
                    sections.append("2. Espacio aéreo: Corredor aéreo local despejado.")
                if quakes:
                    sections.append(f"3. Sensores sísmicos: {len(quakes)} sismos >= M4.5 en las últimas 24h.")
                else:
                    sections.append("3. Sensores sísmicos: Corteza terrestre estable sin anomalías mayores.")
                if sw:
                    sections.append(f"4. Clima espacial: Índice Kp {sw.kp_index:.1f} ({sw.storm_level}).")

                return True, "\n".join(sections)
            elif workspace_cmd == "gemini_live_start":
                from src.darius_ai.core.gemini_live_engine import get_gemini_live_engine

                engine = get_gemini_live_engine()
                import asyncio
                import threading

                threading.Thread(target=lambda: asyncio.run(engine.start_async()), daemon=True).start()
                return True, "Iniciando enlace neuronal bidireccional con Gemini Live, señor. Canal full-duplex en línea."
            elif workspace_cmd == "gemini_live_stop":
                from src.darius_ai.core.gemini_live_engine import get_gemini_live_engine

                engine = get_gemini_live_engine()
                import asyncio
                import threading

                threading.Thread(target=lambda: asyncio.run(engine.stop_async()), daemon=True).start()
                return True, "Enlace Gemini Live desconectado, señor. Retornando a canal de síntesis estándar."
            elif workspace_cmd == "antigravity_agent_status":
                from src.darius_ai.core.antigravity_bridge import get_antigravity_bridge

                bridge = get_antigravity_bridge()
                if bridge.is_available():
                    return True, "El Agente Antigravity está en línea y vinculado para resolver tareas autónomas, señor."
                return False, "El runtime de Antigravity no está disponible en este entorno, señor."
            fn = action.get("fn")
            if callable(fn):
                res = fn()
                return True, str(res) if res is not None else ""
            return True, ""


        elif open_window:
            if atype == "powershell":
                subprocess.Popen(  # noqa: S603
                    [_PS, "-NoExit", "-Command", run],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(  # noqa: S603
                    [_CMD, "/k", run],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            return True, ""

        elif return_out:
            if atype == "powershell":
                result = subprocess.run(  # noqa: S603
                    [_PS, "-NonInteractive", "-Command", run],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                result = subprocess.run(  # noqa: S603
                    [_CMD, "/c", run], capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
                )
            output = (result.stdout or result.stderr or "Sin salida").strip()
            if len(output) > 300:
                output = output[:300] + "…"
            log.debug(f"[WinCMD] Output: {output[:120]}")
            return True, output

        else:
            if atype == "powershell":
                subprocess.Popen(  # noqa: S603
                    [_PS, "-NonInteractive", "-WindowStyle", "Hidden", "-Command", run],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                subprocess.Popen(  # noqa: S603
                    [_CMD, "/c", run],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            return True, ""

    except subprocess.TimeoutExpired:
        log.error(f"[WinCMD] Timeout: {run[:60]}")
        return False, "El comando tardó demasiado."
    except Exception as e:  # noqa: BLE001
        log.error(f"[WinCMD] Error en run_action: {e}")
        return False, str(e)


def _launch(cmd: str, fallback_cmd: str | None = None) -> bool:
    from pathlib import Path

    # DETACHED_PROCESS garantiza que el proceso hijo es completamente
    # independiente de Darius: no hereda la ventana ni compite por el foco.
    # Esto corrige el bug donde msconfig/taskmgr/regedit abría el reproductor
    # de audio porque el proceso no se desenganchaba del hilo de TTS.
    detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        # 1. URIs de protocolo de Windows (ms-settings:, windowsdefender:, shell:…)
        if re.match(r"^[a-z\-]+:", cmd) and not cmd.endswith(".exe"):
            os.startfile(cmd)  # noqa: S606
            return True
        # 2. Snap-ins de MMC (.msc)
        if cmd.endswith(".msc"):
            subprocess.Popen([_MMC, cmd], creationflags=detached)  # noqa: S603
            return True
        # 3. Applets del Panel de Control (.cpl)
        if cmd.endswith(".cpl"):
            subprocess.Popen([_CONTROL, cmd], creationflags=detached)  # noqa: S603
            return True
        # 4. Ejecutable con ruta absoluta
        if Path(cmd).is_file():
            os.startfile(cmd)  # noqa: S606
            return True
        # 5. Comandos del sistema (msconfig, taskmgr, regedit, calc…)
        #    Se usa shell=True para que Windows los localice en PATH igual que
        #    si el usuario los escribiera en Ejecutar (Win+R). DETACHED evita
        #    que el proceso herede la consola de Darius.
        subprocess.Popen([_CMD, "/c", cmd], creationflags=detached)  # noqa: S603
        return True
    except FileNotFoundError:
        if fallback_cmd:
            try:
                subprocess.Popen([_CMD, "/c", fallback_cmd], creationflags=detached)  # noqa: S603
                return True
            except Exception:  # noqa: BLE001
                log.warning(f"[WinCMD] fallback '{fallback_cmd}' también falló")
        return False
    except Exception as e:  # noqa: BLE001
        log.error(f"[WinCMD] _launch error: {e}")
        return False
