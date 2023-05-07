import ctypes
import os
import sys
from ctypes import wintypes

import keyboard
import psutil
import pystray
from PIL import Image
from dotenv import load_dotenv
load_dotenv()


class DllInjector:
    PROCESS_ALL_ACCESS = 0x1F0FFF
    INVALID_HANDLE_VALUE = -1
    MEM_COMMIT = 0x1000
    MEM_RESERVE = 0x2000
    PAGE_READWRITE = 0x04
    INFINITE = -1


    def __init__(self, dll_path, process_name):
        self.dll_path = dll_path
        self.process_name = process_name

        self.dll = ctypes.CDLL(dll_path)
        self.process_id = self.get_process_id()

    def get_process_id(self):
        for process in psutil.process_iter(['pid', 'name']):
            if process.info['name'] == self.process_name:
                return process.info['pid']
        return None
    
    def find_process(self):
        self.process_id = self.get_process_id()
        if self.process_id is not None:
            return True
        else:
            return False
        

    def open_process(self, process_id):
        PROCESS_ALL_ACCESS = 0x1F0FFF
        INVALID_HANDLE_VALUE = -1

        OpenProcess = ctypes.windll.kernel32.OpenProcess
        OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        OpenProcess.restype = wintypes.HANDLE

        process_handle = OpenProcess(PROCESS_ALL_ACCESS, False, wintypes.DWORD(process_id))
        if process_handle == INVALID_HANDLE_VALUE:
            print("Error al abrir el proceso")
            return None
        return process_handle
    
    def allocate_memory(self, process_handle, size):
        MEM_COMMIT = 0x1000
        MEM_RESERVE = 0x2000
        PAGE_READWRITE = 0x04

        VirtualAllocEx = ctypes.windll.kernel32.VirtualAllocEx
        VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        VirtualAllocEx.restype = wintypes.LPVOID

        memory_address = VirtualAllocEx(process_handle, None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        return memory_address

    def write_memory(self, process_handle, memory_address, data):
        WriteProcessMemory = ctypes.windll.kernel32.WriteProcessMemory
        WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        WriteProcessMemory.restype = wintypes.BOOL

        bytes_written = ctypes.c_size_t()
        WriteProcessMemory(process_handle, memory_address, data, len(data), ctypes.byref(bytes_written))
        return bytes_written.value
    
    def create_remote_thread(self, process_handle, LoadLibraryA, memory_address):
        CreateRemoteThread = ctypes.windll.kernel32.CreateRemoteThread
        CreateRemoteThread.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        CreateRemoteThread.restype = wintypes.HANDLE

        thread_id = wintypes.DWORD()
        thread_handle = CreateRemoteThread(process_handle, None, 0, LoadLibraryA, memory_address, 0, ctypes.byref(thread_id))

        if not thread_handle:
            print("Error al crear el hilo remoto")
            return None
        return thread_handle
    

    def inject_dll(self):
        process_handle = self.open_process(self.process_id)
        if process_handle is None:
            return

        memory_address = self.allocate_memory(process_handle, len(self.dll_path))
        if not memory_address:
            print("Error al asignar memoria")
            ctypes.windll.kernel32.CloseHandle(process_handle)
            return

        bytes_written = self.write_memory(process_handle, memory_address, self.dll_path.encode('utf-8'))
        if bytes_written != len(self.dll_path):
            print("Error al escribir en la memoria")
            ctypes.windll.kernel32.CloseHandle(process_handle)
            return

        LoadLibraryA = ctypes.windll.kernel32.LoadLibraryA
        LoadLibraryA.argtypes = [ctypes.c_char_p]
        LoadLibraryA.restype = wintypes.HMODULE

        thread_handle = self.create_remote_thread(process_handle, LoadLibraryA, memory_address)
        if not thread_handle:
            ctypes.windll.kernel32.CloseHandle(process_handle)
            return

        INFINITE = -1
        ctypes.windll.kernel32.WaitForSingleObject(thread_handle, INFINITE)
        ctypes.windll.kernel32.CloseHandle(thread_handle)
        ctypes.windll.kernel32.CloseHandle(process_handle)

    
    def unload_dll(self):
        # Obtén el módulo inyectado en el proceso
        hModule = self.get_injected_module()

        if hModule:
            # Descarga la DLL del proceso
            self.free_injected_module(hModule)
        else:
            print("No se pudo encontrar el módulo inyectado.")
    
    def get_injected_module(self):
        module_name = os.path.basename(self.dll_path)

        for module in psutil.Process(self.process_id).memory_maps():
            if module_name.lower() in module.path.lower():
                return module.path

        return None

    def free_injected_module(self, hModule):
        FreeLibrary = ctypes.windll.kernel32.FreeLibrary
        FreeLibrary.argtypes = [wintypes.HMODULE]
        FreeLibrary.restype = wintypes.BOOL

        if FreeLibrary(hModule):
            print("DLL descargada exitosamente.")
        else:
            print("Error al descargar la DLL.")



class App:
    def __init__(self, dll_injector):
        self.dll_injector = dll_injector

        
        keyboard.add_hotkey('Alt+I', self.keyboard_shortcut_handler)
        keyboard.add_hotkey('Alt+C', self.close_injector)
        keyboard.add_hotkey('Alt+X', self.close_application)
        keyboard.add_hotkey('Alt+U', self.keyboard_unload_dll_handler)


        # Crea un ícono en la bandeja del sistema
        icon_image = Image.open("icono.png")
        self.systray_icon = pystray.Icon("dll_injector", icon_image, "DLL Injector", menu=pystray.Menu(
        pystray.MenuItem('Inyectar', self.systray_action),
        pystray.MenuItem('Descargar', self.systray_unload_action)  
    ))

    def systray_unload_action(self, icon, item):
        print("Ícono de la bandeja del sistema presionado para descargar DLL")
        if self.dll_injector.find_process():
            self.dll_injector.unload_dll()
        else:
            print("El proceso Target no se encontró. Por favor, inicia el proceso e intenta nuevamente.")


    def keyboard_unload_dll_handler(self):
        print("Atajo de teclado para descargar DLL presionado")
        if self.dll_injector.find_process():
            self.dll_injector.unload_dll()
        else:
            print("El proceso Target no se encontró. Por favor, inicia el proceso e intenta nuevamente.")

    
    def close_application(self):
        # Cierra el proceso Target
        for process in psutil.process_iter(['pid', 'name']):
            if process.info['name'] == os.getenv("PROCESS_NAME"):
                process.terminate()
        
        # Cierra el inyector y el ícono de la bandeja del sistema
        self.close_injector()


    # Función para manejar atajos de teclado
    def keyboard_shortcut_handler(self):
        print("Atajo de teclado presionado")
        if self.dll_injector.find_process():
            self.dll_injector.inject_dll()
        else:
            print("El proceso Target no se encontró. Por favor, inicia el proceso e intenta nuevamente.")

    # Función para cerrar el inyector
    def close_injector(self):
        print("Cerrando el inyector...")
        self.systray_icon.stop()
        sys.exit()

    # Función para manejar acciones de la bandeja del sistema
    def systray_action(self, icon, item):
        # Aquí puedes agregar la lógica que se ejecutará al hacer clic en el ícono de la bandeja del sistema
        print("Ícono de la bandeja del sistema presionado")
        self.dll_injector.inject_dll()

    def run(self):
        # Inicia el ícono de la bandeja del sistema
        self.systray_icon.run()



if __name__ == "__main__":
    dll_path = os.getenv("DLL_PATH")
    process_name = os.getenv("PROCESS_NAME")
    dll_injector = DllInjector(dll_path, process_name)
    app = App(dll_injector)
    app.run()