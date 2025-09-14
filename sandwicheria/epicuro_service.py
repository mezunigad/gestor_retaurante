import os
import sys
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess

class EpicuroService(win32serviceutil.ServiceFramework):
    _svc_name_ = "EpicuroService"
    _svc_display_name_ = "Epicuro Sandwich App Service"
    _svc_description_ = "Servicio para la aplicación Epicuro Sandwich"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYSERVICE_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        # Cambiar al directorio de la aplicación
        os.chdir("C:\\sandwicheria")
        
        # Ejecutar la aplicación
        process = subprocess.Popen([sys.executable, "app.py"], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE)
        
        # Esperar hasta que se detenga el servicio
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        process.terminate()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(EpicuroService)