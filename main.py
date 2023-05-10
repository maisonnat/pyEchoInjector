"""
Injects a DLL into a process.

Args:
    dll_path: The path to the DLL to inject.
    process_name: The name of the process to inject the DLL into.

Raises:
    OSError: If the DLL cannot be found or the process cannot be found.

Example:
    >>> dll_injector = DllInjector("C:\\Windows\\System32\\calc.dll", "calc")
    >>> dll_injector.inject_dll()

"""

import ctypes
import os
import sys
from ctypes import wintypes, Structure

import keyboard
import psutil
import pystray
from PIL import Image


class HMODULE(Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

class DllInjector:
    PROCESS_ALL_ACCESS = 0x1F0FFF
    INVALID_HANDLE_VALUE = -1
    MEM_COMMIT = 0x1000
    MEM_RESERVE = 0x2000
    PAGE_READWRITE = 0x04
    INFINITE = -1


    def __init__(self, dll_path, process_name):
        """
        Initializes the DllInjector object.

        Args:
            dll_path: The path to the DLL to inject.
            process_name: The name of the process to inject the DLL into.

        """
        self.dll_path = dll_path
        self.process_name = process_name

        self.dll = ctypes.CDLL(dll_path)
        self.target_process_id = self.get_target_process_id()


    def get_target_process_id(self):
        """
        Gets the process ID of the process with the given name.

        Returns:
            The process ID of the process with the given name.

        Raises:
            OSError: If the process cannot be found.

        """
        for process in psutil.process_iter(['pid', 'name']):
            if process.info['name'] == self.process_name:
                return process.info['pid']
        raise OSError("Process not found.")


    def open_process(self, target_process_id):
        """
        Opens a handle to the process with the given ID.

        Args:
            target_process_id: The process ID of the process to open a handle to.

        Returns:
            The handle to the process.

        Raises:
            OSError: If the process cannot be found or the handle cannot be opened.

        """
        PROCESS_ALL_ACCESS = 0x1F0FFF
        INVALID_HANDLE_VALUE = -1

        OpenProcess = ctypes.windll.kernel32.OpenProcess
        OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        OpenProcess.restype = wintypes.HANDLE

        process_handle = OpenProcess(PROCESS_ALL_ACCESS, False, target_process_id)
        if process_handle == INVALID_HANDLE_VALUE:
            raise OSError("Process not found or handle cannot be opened.")
        return process_handle


    def allocate_memory(self, process_handle, size):
        """
        Allocates memory in the process with the given handle.

        Args:
            process_handle: The handle to the process to allocate memory in.
            size: The size of the memory to allocate.

        Returns:
            The address of the allocated memory.

        Raises:
            OSError: If the memory cannot be allocated.

        """
        MEM_COMMIT = 0x1000
        MEM_RESERVE = 0x2000
        PAGE_READWRITE = 0x04

        VirtualAllocEx = ctypes.windll.kernel32.VirtualAllocEx
        VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        VirtualAllocEx.restype = wintypes.LPVOID

        memory_address = VirtualAllocEx(process_handle, None, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        return memory_address

    def write_memory(self, process_handle, memory_address, data):
        """
        Writes data to the memory location with the given address in the process with the given handle.

        Args:
            process_handle: The handle to the process to write to.
            memory_address: The address of the memory location to write to.
            data: The data to write.

        Raises:
            OSError: If the memory cannot be written to.

        """
        WriteProcessMemory = ctypes.windll.kernel32.WriteProcessMemory
        WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        WriteProcessMemory.restype = wintypes.BOOL

        bytes_written = ctypes.c_size_t()
        WriteProcessMemory(process_handle, memory_address, data, len(data), ctypes.byref(bytes_written))
        return bytes_written.value
    
    def create_remote_thread(self, process_handle, LoadLibraryA, memory_address):
        """
        Creates a remote thread in the process with the given handle.

        Args:
            process_handle: The handle to the process to create the thread in.
            LoadLibraryA: The address of the LoadLibraryA function.
            memory_address: The address of the DLL to load.

        Returns:
            The handle to the remote thread.

        Raises:
            OSError: If the thread cannot be created.

        """
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
        """
        Injects the DLL into the process with the given name.

        Raises:
            OSError: If the DLL cannot be injected.

        """
        process_handle = self.open_process(self.target_process_id)
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
        """
        Unloads the DLL from the process with the given name.

        Raises:
            OSError: If the DLL cannot be unloaded.

        """
        # Obtén el módulo inyectado en el proceso
        hModule = self.get_injected_module()

        if hModule:
            # Descarga la DLL del proceso
            self.free_injected_module(hModule)
        else:
            print("No se pudo encontrar el módulo inyectado.")
    
    def get_injected_module(self):
        module_name = os.path.basename(self.dll_path)

        for module in psutil.Process(self.target_process_id).memory_maps():
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
    dll_path = os.environ["DLL_PATH"]
    process_name = os.environ["PROCESS_NAME"]
    dll_injector = DllInjector(dll_path, process_name)
    app = App(dll_injector)
    app.run()