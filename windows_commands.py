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
            "configuraciones de red", "ajustes de red", "red e internet",
            "configurar red", "opciones de red", "conexiones de red",
            "configuracion de internet", "ajustes de internet",
            "internet y red", "red wifi", "configuracion wifi"
        ],
        "desc": "Configuración de Red e Internet"
    },
    "wifi": {
        "cmd": "ms-settings:network-wifi",
        "aliases": ["configuracion wifi", "ajustes wifi", "redes wifi", "conectar wifi"],
        "desc": "Configuración WiFi"
    },
    "vpn": {
        "cmd": "ms-settings:network-vpn",
        "aliases": ["configurar vpn", "ajustes vpn"],
        "desc": "Configuración VPN"
    },
    "ethernet": {
        "cmd": "ms-settings:network-ethernet",
        "aliases": ["conexion ethernet", "cable de red", "red cableada"],
        "desc": "Configuración Ethernet"
    },
    "proxy": {
        "cmd": "ms-settings:network-proxy",
        "aliases": ["configuracion proxy", "ajustes proxy"],
        "desc": "Configuración de Proxy"
    },
    "estado de red": {
        "cmd": "ms-settings:network-status",
        "aliases": ["estado de conexion", "ver estado de red", "diagnostico de red"],
        "desc": "Estado de la red"
    },
    "adaptadores de red": {
        "cmd": "ncpa.cpl",
        "aliases": [
            "ver adaptadores", "conexiones de red clasico",
            "propiedades de red", "adaptador de red"
        ],
        "desc": "Conexiones de red (adaptadores)"
    },
    "aplicaciones y caracteristicas": {
        "cmd": "ms-settings:appsfeatures",
        "aliases": [
            "aplicaciones y características", "apps y caracteristicas",
            "apps instaladas", "programas instalados", "desinstalar programas",
            "administrar aplicaciones", "gestionar apps", "ver aplicaciones",
            "aplicaciones del sistema", "lista de aplicaciones",
            "aplicaciones y caracteristicas de windows"
        ],
        "desc": "Aplicaciones y características"
    },
    "aplicaciones predeterminadas": {
        "cmd": "ms-settings:defaultapps",
        "aliases": ["apps predeterminadas", "programas predeterminados", "aplicaciones por defecto"],
        "desc": "Aplicaciones predeterminadas"
    },
    "inicio automatico": {
        "cmd": "ms-settings:startupapps",
        "aliases": ["aplicaciones de inicio", "apps al iniciar", "programas de inicio", "inicio de windows"],
        "desc": "Aplicaciones de inicio"
    },
    "caracteristicas opcionales": {
        "cmd": "ms-settings:optionalfeatures",
        "aliases": ["funciones opcionales", "características de windows", "agregar características"],
        "desc": "Características opcionales de Windows"
    },
    "programas y caracteristicas clasico": {
        "cmd": "appwiz.cpl",
        "aliases": ["desinstalar programas clasico", "agregar o quitar programas", "appwiz"],
        "desc": "Programas y características (Panel de Control)"
    },
    "configuracion": {
        "cmd": "ms-settings:",
        "aliases": ["ajustes de windows", "settings de windows", "opciones del sistema"],
        "desc": "Configuración de Windows"
    },
    "pantalla": {
        "cmd": "ms-settings:display",
        "aliases": [
            "configuracion de pantalla", "ajustes de pantalla",
            "resolucion de pantalla", "brillo de pantalla", "configurar monitor"
        ],
        "desc": "Configuración de pantalla"
    },
    "sonido": {
        "cmd": "ms-settings:sound",
        "aliases": [
            "configuracion de sonido", "ajustes de audio", "volumen del sistema",
            "dispositivos de audio", "salida de audio", "entrada de audio"
        ],
        "desc": "Configuración de sonido"
    },
    "notificaciones": {
        "cmd": "ms-settings:notifications",
        "aliases": [
            "configuracion de notificaciones", "ajustes de notificaciones",
            "alertas del sistema", "centro de notificaciones"
        ],
        "desc": "Notificaciones y acciones"
    },
    "energia": {
        "cmd": "ms-settings:powersleep",
        "aliases": [
            "configuracion de energia", "plan de energia", "ahorro de bateria",
            "opciones de energia"
        ],
        "desc": "Energía y suspensión"
    },
    "almacenamiento": {
        "cmd": "ms-settings:storagesense",
        "aliases": [
            "configuracion de almacenamiento", "sensor de almacenamiento",
            "storage sense"
        ],
        "desc": "Almacenamiento"
    },
    "informacion del sistema": {
        "cmd": "ms-settings:about",
        "aliases": [
            "acerca de este pc", "acerca del equipo", "informacion del equipo",
            "version de windows", "especificaciones del sistema", "sobre este pc"
        ],
        "desc": "Acerca de este equipo"
    },
    "multitarea": {
        "cmd": "ms-settings:multitasking",
        "aliases": ["configuracion de multitarea", "escritorios virtuales", "snap windows"],
        "desc": "Multitarea"
    },
    "personalizacion": {
        "cmd": "ms-settings:personalization",
        "aliases": ["personalizar windows", "temas de windows", "aspecto del sistema"],
        "desc": "Personalización"
    },
    "fondo de pantalla": {
        "cmd": "ms-settings:personalization-background",
        "aliases": ["cambiar fondo", "wallpaper", "imagen de fondo"],
        "desc": "Fondo de pantalla"
    },
    "colores": {
        "cmd": "ms-settings:colors",
        "aliases": ["colores de windows", "color de acento", "modo oscuro", "tema oscuro", "dark mode"],
        "desc": "Colores y modo oscuro"
    },
    "temas": {
        "cmd": "ms-settings:themes",
        "aliases": ["temas de windows", "cambiar tema de windows"],
        "desc": "Temas"
    },
    "pantalla de bloqueo": {
        "cmd": "ms-settings:lockscreen",
        "aliases": ["configurar pantalla de bloqueo", "lock screen"],
        "desc": "Pantalla de bloqueo"
    },
    "barra de tareas": {
        "cmd": "ms-settings:taskbar",
        "aliases": ["configurar barra de tareas", "taskbar windows"],
        "desc": "Barra de tareas"
    },
    "cuentas": {
        "cmd": "ms-settings:accounts",
        "aliases": ["configuracion de cuentas", "mi cuenta windows", "cuenta de usuario windows"],
        "desc": "Cuentas"
    },
    "opciones de inicio de sesion": {
        "cmd": "ms-settings:signinoptions",
        "aliases": [
            "contraseña de windows", "pin de windows", "hello windows",
            "huella dactilar", "cambiar contraseña windows"
        ],
        "desc": "Opciones de inicio de sesión"
    },
    "otros usuarios": {
        "cmd": "ms-settings:otherusers",
        "aliases": ["usuarios del sistema", "agregar usuario windows", "administrar usuarios windows"],
        "desc": "Otros usuarios"
    },
    "fecha y hora": {
        "cmd": "ms-settings:dateandtime",
        "aliases": ["configurar fecha y hora", "zona horaria", "ajustar reloj"],
        "desc": "Fecha y hora"
    },
    "idioma y region": {
        "cmd": "ms-settings:regionlanguage",
        "aliases": ["configurar idioma windows", "cambiar idioma windows", "idioma del sistema"],
        "desc": "Idioma y región"
    },
    "bluetooth": {
        "cmd": "ms-settings:bluetooth",
        "aliases": [
            "configuracion bluetooth", "activar bluetooth",
            "dispositivos bluetooth", "emparejar bluetooth"
        ],
        "desc": "Bluetooth y otros dispositivos"
    },
    "impresoras": {
        "cmd": "ms-settings:printers",
        "aliases": ["agregar impresora", "configurar impresora", "impresoras y escáneres"],
        "desc": "Impresoras y escáneres"
    },
    "mouse": {
        "cmd": "ms-settings:mousetouchpad",
        "aliases": ["configurar mouse", "ajustes del raton", "touchpad windows", "panel táctil windows"],
        "desc": "Mouse y panel táctil"
    },
    "teclado windows": {
        "cmd": "ms-settings:typing",
        "aliases": ["configurar teclado windows", "ajustes del teclado windows"],
        "desc": "Escritura y teclado"
    },
    "privacidad": {
        "cmd": "ms-settings:privacy",
        "aliases": ["configuracion de privacidad", "permisos de aplicaciones", "privacidad de windows"],
        "desc": "Privacidad y seguridad"
    },
    "seguridad de windows": {
        "cmd": "windowsdefender:",
        "aliases": ["windows defender", "antivirus windows", "proteccion contra virus", "defender"],
        "desc": "Seguridad de Windows / Defender"
    },
    "actualizaciones": {
        "cmd": "ms-settings:windowsupdate",
        "aliases": [
            "windows update", "actualizar windows", "buscar actualizaciones windows",
            "actualizaciones de windows", "instalar actualizaciones windows"
        ],
        "desc": "Windows Update"
    },
    "panel de control": {
        "cmd": "control",
        "aliases": ["panel del sistema windows", "control panel"],
        "desc": "Panel de Control"
    },
    "administrador de dispositivos": {
        "cmd": "devmgmt.msc",
        "aliases": [
            "device manager", "gestor de dispositivos",
            "controladores windows", "drivers windows", "hardware del sistema"
        ],
        "desc": "Administrador de dispositivos"
    },
    "administrador de discos": {
        "cmd": "diskmgmt.msc",
        "aliases": ["disk management", "gestionar discos windows", "particiones disco"],
        "desc": "Administración de discos"
    },
    "servicios windows": {
        "cmd": "services.msc",
        "aliases": ["servicios de windows", "gestionar servicios windows"],
        "desc": "Servicios de Windows"
    },
    "editor del registro": {
        "cmd": "regedit",
        "aliases": ["regedit", "registro de windows", "registro del sistema windows"],
        "desc": "Editor del Registro"
    },
    "configuracion del sistema": {
        "cmd": "msconfig",
        "aliases": [
            "msconfig", "ms config", "ms confi", "configuracion de arranque",
            "inicio del sistema windows", "herramienta msconfig"
        ],
        "desc": "Configuración del sistema (msconfig)"
    },
    "informacion del sistema detallada": {
        "cmd": "msinfo32",
        "aliases": ["msinfo32", "msinfo", "informacion detallada del sistema windows"],
        "desc": "Información del sistema"
    },
    "administrador de tareas": {
        "cmd": "taskmgr",
        "aliases": ["task manager", "procesos del sistema windows", "uso de cpu windows"],
        "desc": "Administrador de tareas"
    },
    "monitor de rendimiento": {
        "cmd": "perfmon",
        "aliases": ["rendimiento del sistema windows", "performance monitor"],
        "desc": "Monitor de rendimiento"
    },
    "monitor de recursos": {
        "cmd": "resmon",
        "aliases": ["resource monitor", "uso de recursos windows"],
        "desc": "Monitor de recursos"
    },
    "visor de eventos": {
        "cmd": "eventvwr",
        "aliases": ["event viewer", "registro de eventos windows", "logs del sistema windows"],
        "desc": "Visor de eventos"
    },
    "programador de tareas": {
        "cmd": "taskschd.msc",
        "aliases": ["task scheduler", "tareas programadas windows"],
        "desc": "Programador de tareas"
    },
    "limpieza de disco": {
        "cmd": "cleanmgr",
        "aliases": ["limpiar disco windows", "disk cleanup", "liberador de espacio"],
        "desc": "Liberador de espacio en disco"
    },
    "desfragmentar": {
        "cmd": "dfrgui",
        "aliases": ["desfragmentar disco windows", "optimizar unidades", "optimizar disco windows"],
        "desc": "Desfragmentación y optimización"
    },
    "simbolo del sistema": {
        "cmd": "cmd",
        "aliases": ["consola cmd", "terminal cmd", "linea de comandos windows", "command prompt"],
        "desc": "Símbolo del sistema"
    },
    "powershell": {
        "cmd": "powershell",
        "aliases": ["power shell windows", "terminal powershell", "consola powershell"],
        "desc": "Windows PowerShell"
    },
    "terminal de windows": {
        "cmd": "wt",
        "aliases": ["windows terminal", "terminal moderna windows"],
        "desc": "Terminal de Windows"
    },
    "explorador de archivos": {
        "cmd": "explorer",
        "aliases": ["explorador windows", "mis archivos", "file explorer"],
        "desc": "Explorador de archivos"
    },
    "descargas": {
        "cmd": "shell:Downloads",
        "aliases": ["carpeta descargas", "mis descargas", "downloads folder"],
        "desc": "Carpeta Descargas"
    },
    "documentos": {
        "cmd": "shell:Personal",
        "aliases": ["mis documentos", "carpeta documentos windows"],
        "desc": "Documentos"
    },
    "escritorio": {
        "cmd": "shell:Desktop",
        "aliases": ["abrir escritorio windows", "mostrar escritorio"],
        "desc": "Escritorio"
    },
    "papelera": {
        "cmd": "shell:RecycleBinFolder",
        "aliases": ["papelera de reciclaje", "recycle bin windows", "archivos eliminados windows"],
        "desc": "Papelera de reciclaje"
    },
    "brave": {
        "cmd": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "fallback_cmd": "start brave",
        "aliases": ["brave browser", "navegador brave", "brave software"],
        "desc": "Brave Browser"
    },
    "chrome": {
        "cmd": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "fallback_cmd": "start chrome",
        "aliases": ["google chrome", "navegador chrome", "chrome browser"],
        "desc": "Google Chrome"
    },
    "firefox": {
        "cmd": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "fallback_cmd": "start firefox",
        "aliases": ["mozilla firefox", "navegador firefox", "mozilla browser"],
        "desc": "Mozilla Firefox"
    },
    "edge": {
        "cmd": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "fallback_cmd": "start msedge",
        "aliases": ["microsoft edge", "navegador edge", "msedge browser"],
        "desc": "Microsoft Edge"
    },
    "tienda": {
        "cmd": "ms-windows-store:",
        "aliases": ["microsoft store", "tienda de windows", "windows store"],
        "desc": "Microsoft Store"
    },
    "calculadora": {
        "cmd": "calc",
        "aliases": ["abrir calculadora windows", "calculator windows"],
        "desc": "Calculadora"
    },
    "bloc de notas": {
        "cmd": "notepad",
        "aliases": ["notepad windows", "editor de texto simple windows"],
        "desc": "Bloc de notas"
    },
    "paint": {
        "cmd": "mspaint",
        "aliases": ["microsoft paint", "ms paint windows"],
        "desc": "Paint"
    },
    "recortes": {
        "cmd": "snippingtool",
        "aliases": ["herramienta de recortes", "snipping tool", "captura de pantalla windows"],
        "desc": "Herramienta Recortes"
    },
    "lupa": {
        "cmd": "magnify",
        "aliases": ["magnificador windows", "zoom de pantalla windows"],
        "desc": "Lupa"
    },
    "teclado en pantalla": {
        "cmd": "osk",
        "aliases": ["teclado virtual windows", "teclado tactil windows", "on screen keyboard"],
        "desc": "Teclado en pantalla"
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  TIPO B — SUBPROCESOS / ACCIONES DEL SISTEMA
# ═════════════════════════════════════════════════════════════════════════════

SYSTEM_ACTIONS: dict[str, dict] = {

    "diagnosticar red": {
        "action": {"type": "cmd", "run": "msdt.exe /id NetworkDiagnosticsNetworkAdapter"},
        "aliases": [
            "reparar red", "solucionar problemas de red", "arreglar internet",
            "diagnostico de conexion", "reparar conexion", "internet no funciona"
        ],
        "desc": "Diagnóstico automático de red"
    },
    "ver ip": {
        "action": {"type": "powershell",
                   "run": "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | Select-Object -First 1).IPAddress"},
        "aliases": ["cual es mi ip", "mi direccion ip", "ver direccion ip", "ip local", "mostrar ip"],
        "desc": "Consultar IP local",
        "return_output": True
    },
    "ver ip publica": {
        "action": {"type": "powershell",
                   "run": "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing).Content"},
        "aliases": ["ip publica", "mi ip externa", "cual es mi ip publica", "ip de internet"],
        "desc": "Consultar IP pública",
        "return_output": True
    },
    "ver dns": {
        "action": {"type": "powershell",
                   "run": "Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses} | Select-Object InterfaceAlias, ServerAddresses | Format-Table -AutoSize | Out-String"},
        "aliases": ["que dns tengo configurado", "ver servidores dns", "mis dns actuales", "mostrar dns"],
        "desc": "Ver servidores DNS configurados",
        "return_output": True
    },
    "limpiar cache dns": {
        "action": {"type": "cmd", "run": "ipconfig /flushdns"},
        "aliases": ["flush dns", "borrar cache dns", "vaciar cache dns", "limpiar dns", "resetear dns"],
        "desc": "Limpiar caché DNS"
    },
    "renovar ip": {
        "action": {"type": "cmd", "run": "ipconfig /release && ipconfig /renew"},
        "aliases": ["renovar direccion ip", "refrescar ip dhcp", "obtener nueva ip dhcp"],
        "desc": "Renovar dirección IP (DHCP)"
    },
    "ver conexiones activas": {
        "action": {"type": "cmd", "run": "netstat -ano"},
        "aliases": ["conexiones de red activas", "puertos abiertos sistema", "mostrar netstat", "ver puertos abiertos"],
        "desc": "Ver conexiones de red activas",
        "return_output": True,
        "open_window": True
    },
    "probar internet": {
        "action": {"type": "cmd", "run": "ping google.com -n 4"},
        "aliases": ["hacer ping a google", "probar conexion a internet", "test de conexion internet",
                    "hay conexion a internet", "hay internet", "verificar internet", "ping google"],
        "desc": "Ping a Google (prueba de conexión)",
        "return_output": True,
        "open_window": True
    },
    "resetear red": {
        "action": {"type": "cmd",
                   "run": "netsh winsock reset && netsh int ip reset && ipconfig /flushdns"},
        "aliases": ["resetear configuracion de red", "reiniciar configuracion red",
                    "restablecer red completa", "reparar tcp ip winsock"],
        "desc": "Restablecer configuración de red (Winsock + TCP/IP + DNS)",
        "confirm": True
    },
    "ver redes wifi": {
        "action": {"type": "cmd", "run": "netsh wlan show networks"},
        "aliases": ["redes wifi disponibles", "ver redes disponibles wifi", "que redes wifi hay",
                    "escanear wifi", "mostrar redes inalambricas"],
        "desc": "Ver redes WiFi disponibles",
        "return_output": True,
        "open_window": True
    },
    "desconectar wifi": {
        "action": {"type": "cmd", "run": "netsh wlan disconnect"},
        "aliases": ["desconectar de la red wifi", "cortar conexion wifi", "desactivar wifi"],
        "desc": "Desconectar del WiFi",
        "confirm": True
    },
    "vaciar papelera": {
        "action": {"type": "powershell",
                   "run": "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"},
        "aliases": ["limpiar papelera de reciclaje", "borrar papelera reciclaje", "vaciar reciclaje"],
        "desc": "Vaciar la papelera de reciclaje",
        "confirm": True
    },
    "ver espacio en disco": {
        "action": {"type": "powershell",
                   "run": "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Usado(GB)';E={[math]::Round(($_.Used/1GB),1)}}, @{N='Libre(GB)';E={[math]::Round(($_.Free/1GB),1)}}, @{N='Total(GB)';E={[math]::Round((($_.Used+$_.Free)/1GB),1)}} | Format-Table -AutoSize | Out-String"},
        "aliases": [
            "espacio disponible en disco", "cuanto espacio libre tengo en disco",
            "espacio libre en disco", "ver estado del disco duro", "capacidad del disco duro",
            "cuanto espacio queda en el disco"
        ],
        "desc": "Ver espacio en disco",
        "return_output": True
    },
    "ver uso de ram": {
        "action": {"type": "powershell",
                   "run": "$os=Get-CimInstance Win32_OperatingSystem; $total=[math]::Round($os.TotalVisibleMemorySize/1MB,1); $libre=[math]::Round($os.FreePhysicalMemory/1MB,1); $usado=[math]::Round($total-$libre,1); \"RAM total: ${total} GB | Usada: ${usado} GB | Libre: ${libre} GB\""},
        "aliases": ["uso de memoria ram", "cuanta ram tengo disponible", "memoria ram libre",
                    "ram disponible ahora", "cuanta memoria usa el sistema"],
        "desc": "Ver uso de memoria RAM",
        "return_output": True
    },
    "ver uso de cpu": {
        "action": {"type": "powershell",
                   "run": "$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; \"Uso de CPU: ${cpu}%\""},
        "aliases": ["uso del procesador ahora", "carga del cpu ahora", "cuanto cpu usa el sistema",
                    "porcentaje de cpu", "rendimiento del procesador"],
        "desc": "Ver uso de CPU",
        "return_output": True
    },
    "ver procesos": {
        "action": {"type": "powershell",
                   "run": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB,0)}} | Format-Table -AutoSize | Out-String"},
        "aliases": ["top procesos del sistema", "procesos que consumen mas recursos",
                    "que proceso esta usando el cpu", "mostrar procesos activos"],
        "desc": "Top 10 procesos por consumo de CPU",
        "return_output": True
    },
    "ver temperatura": {
        "action": {"type": "powershell",
                   "run": "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' | Select-Object @{N='Zona';E={$_.InstanceName}}, @{N='Temperatura(C)';E={[math]::Round($_.CurrentTemperature/10 - 273.15, 1)}} | Format-Table | Out-String"},
        "aliases": ["temperatura del procesador ahora", "temperatura del cpu",
                    "cuanto calor tiene el pc", "temperatura del equipo"],
        "desc": "Ver temperatura del sistema",
        "return_output": True
    },
    "tiempo encendido": {
        "action": {"type": "powershell",
                   "run": "$uptime = (Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime; \"El equipo lleva encendido: $($uptime.Days) dias, $($uptime.Hours) horas y $($uptime.Minutes) minutos\""},
        "aliases": ["cuanto tiempo lleva encendido el pc", "tiempo de actividad del sistema",
                    "uptime del sistema", "desde cuando esta encendido el equipo"],
        "desc": "Tiempo de actividad del sistema",
        "return_output": True
    },
    "limpiar archivos temporales": {
        "action": {"type": "powershell",
                   "run": "Remove-Item -Path $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Path 'C:\\Windows\\Temp\\*' -Recurse -Force -ErrorAction SilentlyContinue; 'Archivos temporales eliminados.'"},
        "aliases": ["borrar archivos temporales", "limpiar carpeta temp", "eliminar temporales del sistema",
                    "limpiar cache del sistema operativo"],
        "desc": "Limpiar archivos temporales",
        "confirm": True
    },
    "ver version de windows": {
        "action": {"type": "powershell",
                   "run": "$v = Get-CimInstance Win32_OperatingSystem; \"$($v.Caption) - Build $($v.BuildNumber) - $($v.OSArchitecture)\""},
        "aliases": ["que version de windows tengo instalada", "version actual de windows",
                    "build de windows instalado", "numero de version de windows"],
        "desc": "Ver versión de Windows",
        "return_output": True
    },
    "ver numero de serie": {
        "action": {"type": "powershell",
                   "run": "(Get-CimInstance Win32_BIOS).SerialNumber"},
        "aliases": ["serial del equipo", "numero de serie del equipo", "serial number del pc"],
        "desc": "Ver número de serie del equipo",
        "return_output": True
    },
    "ver modelo del equipo": {
        "action": {"type": "powershell",
                   "run": "$c=Get-CimInstance Win32_ComputerSystem; \"$($c.Manufacturer) $($c.Model)\""},
        "aliases": ["modelo del pc", "que modelo de pc tengo", "marca y modelo del equipo",
                    "fabricante del equipo"],
        "desc": "Ver modelo del equipo",
        "return_output": True
    },
    "ver procesador": {
        "action": {"type": "powershell",
                   "run": "(Get-CimInstance Win32_Processor).Name"},
        "aliases": ["que procesador tengo instalado", "cpu del equipo", "modelo del procesador instalado"],
        "desc": "Ver información del procesador",
        "return_output": True
    },
    "hibernar equipo": {
        "action": {"type": "cmd", "run": "shutdown /h"},
        "aliases": ["poner en hibernacion el equipo", "modo hibernacion pc", "hibernar pc"],
        "desc": "Hibernar el equipo",
        "confirm": True
    },
    "suspender equipo": {
        "action": {"type": "powershell",
                   "run": "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"},
        "aliases": ["modo suspension del equipo", "poner en suspension el pc",
                    "sleep mode pc", "dormir el equipo", "suspender el pc"],
        "desc": "Suspender el equipo",
        "confirm": True
    },
    "bloquear pantalla": {
        "action": {"type": "cmd", "run": "rundll32.exe user32.dll,LockWorkStation"},
        "aliases": ["bloquear el pc", "bloquear el equipo", "bloquear sesion windows",
                    "activar pantalla de bloqueo", "lock screen windows"],
        "desc": "Bloquear la pantalla"
    },
    "cerrar sesion": {
        "action": {"type": "cmd", "run": "shutdown /l"},
        "aliases": ["cerrar la sesion de windows", "log off windows",
                    "salir de la sesion de usuario", "cerrar cuenta de usuario"],
        "desc": "Cerrar sesión",
        "confirm": True
    },
    "apagar monitor": {
        "action": {"type": "cmd", "run": r'nircmd.exe monitor off'},
        "aliases": ["apagar la pantalla", "apagar el monitor", "poner monitor en standby",
                    "apagar display"],
        "desc": "Apagar el monitor"
    },
    "ver servicios activos": {
        "action": {"type": "powershell",
                   "run": "Get-Service | Where-Object {$_.Status -eq 'Running'} | Sort-Object DisplayName | Select-Object DisplayName, Status | Format-Table -AutoSize | Out-String"},
        "aliases": ["servicios windows en ejecucion", "que servicios estan corriendo",
                    "mostrar servicios activos del sistema"],
        "desc": "Ver servicios activos del sistema",
        "return_output": True,
        "open_window": True
    },
    "buscar actualizaciones ahora": {
        "action": {"type": "powershell", "run": "Start-Process ms-settings:windowsupdate-action"},
        "aliases": ["actualizar windows ahora", "descargar actualizaciones ahora",
                    "instalar actualizaciones windows ahora"],
        "desc": "Buscar e instalar actualizaciones ahora"
    },
    "activar firewall": {
        "action": {"type": "cmd", "run": "netsh advfirewall set allprofiles state on"},
        "aliases": ["encender el firewall de windows", "habilitar firewall windows",
                    "activar cortafuegos windows"],
        "desc": "Activar el Firewall de Windows",
        "confirm": True
    },
    "desactivar firewall": {
        "action": {"type": "cmd", "run": "netsh advfirewall set allprofiles state off"},
        "aliases": ["apagar el firewall de windows", "deshabilitar firewall windows",
                    "desactivar cortafuegos windows"],
        "desc": "Desactivar el Firewall de Windows",
        "confirm": True
    },
    "ver estado del firewall": {
        "action": {"type": "cmd", "run": "netsh advfirewall show allprofiles state"},
        "aliases": ["estado actual del firewall", "esta activo el firewall windows",
                    "ver si el firewall esta encendido"],
        "desc": "Ver estado del Firewall",
        "return_output": True,
        "open_window": True
    },
    "ver archivos grandes": {
        "action": {"type": "powershell",
                   "run": "Get-ChildItem C:\\ -Recurse -ErrorAction SilentlyContinue | Sort-Object Length -Descending | Select-Object -First 10 FullName, @{N='Tamaño(MB)';E={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize | Out-String"},
        "aliases": ["archivos que ocupan mas espacio en disco", "top archivos pesados",
                    "buscar archivos grandes en el disco"],
        "desc": "Ver los 10 archivos más grandes en C:",
        "return_output": True,
        "open_window": True
    },
    "resumen del sistema": {
        "action": {"type": "powershell",
                   "run": """
$cpu    = (Get-CimInstance Win32_Processor).Name
$ram    = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB, 1)
$os     = (Get-CimInstance Win32_OperatingSystem).Caption
$uptime = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$ip     = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | Select-Object -First 1).IPAddress
"SO: $os`nCPU: $cpu`nRAM: $ram GB`nIP local: $ip`nActivo hace: $($uptime.Hours)h $($uptime.Minutes)m"
"""},
        "aliases": [
            "informacion tecnica del sistema", "resumen tecnico del equipo",
            "como esta el equipo ahora", "estado tecnico del equipo",
            "informe del sistema operativo"
        ],
        "desc": "Resumen técnico del sistema",
        "return_output": True
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  MOTOR DE RESOLUCIÓN
# ═════════════════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    for src, dst in zip("áéíóúüñàèìòù", "aeiouunaeiou", strict=True):
        text = text.replace(src, dst)
    return text.lower().strip()


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
    success  = _launch(cmd, fallback)
    return desc if success else None


def resolve_action(query: str) -> dict | None:
    canonical = _resolve(query, _ACT_TABLE, _ACT_KEYS, _ACT_CUTOFF)
    if canonical:
        entry = SYSTEM_ACTIONS[canonical].copy()
        entry["canonical"] = canonical
        return entry
    return None


def run_action(action_entry: dict) -> tuple[bool, str]:
    action      = action_entry["action"]
    atype       = action["type"]
    run         = action.get("run", "")
    return_out  = action_entry.get("return_output", False)
    open_window = action_entry.get("open_window", False)

    try:
        if open_window:
            if atype == "powershell":
                subprocess.Popen([_PS, "-NoExit", "-Command", run],  # noqa: S603,S607
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen([_CMD, "/k", run],  # noqa: S603,S607
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True, ""

        elif return_out:
            if atype == "powershell":
                result = subprocess.run(  # noqa: S603
                    [_PS, "-NonInteractive", "-Command", run],  # noqa: S607
                    capture_output=True, text=True, timeout=15,
                    encoding="utf-8", errors="replace"
                )
            else:
                result = subprocess.run(  # noqa: S603
                    [_CMD, "/c", run],  # noqa: S607
                    capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace"
                )
            output = (result.stdout or result.stderr or "Sin salida").strip()
            if len(output) > 300:
                output = output[:300] + "…"
            log.debug(f"[WinCMD] Output: {output[:120]}")
            return True, output

        else:
            if atype == "powershell":
                subprocess.Popen(  # noqa: S603
                    [_PS, "-NonInteractive", "-WindowStyle", "Hidden", "-Command", run],  # noqa: S607
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([_CMD, "/c", run],  # noqa: S603,S607
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            return True, ""

    except subprocess.TimeoutExpired:
        log.error(f"[WinCMD] Timeout: {run[:60]}")
        return False, "El comando tardó demasiado."
    except Exception as e:
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
            subprocess.Popen([_MMC, cmd], creationflags=detached)  # noqa: S603,S607
            return True
        # 3. Applets del Panel de Control (.cpl)
        if cmd.endswith(".cpl"):
            subprocess.Popen([_CONTROL, cmd], creationflags=detached)  # noqa: S603,S607
            return True
        # 4. Ejecutable con ruta absoluta
        if Path(cmd).is_file():
            os.startfile(cmd)  # noqa: S606
            return True
        # 5. Comandos del sistema (msconfig, taskmgr, regedit, calc…)
        #    Se usa shell=True para que Windows los localice en PATH igual que
        #    si el usuario los escribiera en Ejecutar (Win+R). DETACHED evita
        #    que el proceso herede la consola de Darius.
        subprocess.Popen([_CMD, "/c", cmd], creationflags=detached)  # noqa: S603,S607
        return True
    except FileNotFoundError:
        if fallback_cmd:
            try:
                subprocess.Popen([_CMD, "/c", fallback_cmd], creationflags=detached)  # noqa: S603,S607
                return True
            except Exception:
                log.warning(f"[WinCMD] fallback '{fallback_cmd}' también falló")
        return False
    except Exception as e:
        log.error(f"[WinCMD] _launch error: {e}")
        return False
