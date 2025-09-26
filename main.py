import eel
import json
import os
import subprocess
import psutil
import platform
from datetime import datetime
from os.path import abspath

# Инициализация Eel
eel.init(abspath('web'))


class ServerManager:
    def __init__(self):
        self.servers_file = 'servers.json'
        self.servers = self.load_servers()
        self.processes = {}

    def load_servers(self):
        """Загрузка серверов из JSON файла"""
        if os.path.exists(self.servers_file):
            try:
                with open(self.servers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Добавляем отсутствующие поля для совместимости
                    for server in data:
                        if 'stop_method' not in server:
                            server['stop_method'] = 'stop_command'
                        if 'display_cmd' not in server:
                            server['display_cmd'] = False
                    return data
            except Exception as e:
                print(f"Ошибка загрузки серверов: {e}")
                return []
        return []

    def save_servers(self):
        """Сохранение серверов в JSON файл"""
        with open(self.servers_file, 'w', encoding='utf-8') as f:
            json.dump(self.servers, f, ensure_ascii=False, indent=2)

    def add_server(self, name, bat_path, description, icon_path=None, stop_method='stop_command', display_cmd=False):
        """Добавление нового сервера"""
        server = {
            'id': len(self.servers) + 1,
            'name': name,
            'bat_path': bat_path,
            'description': description,
            'icon_path': icon_path,
            'stop_method': stop_method,
            'display_cmd': display_cmd,
            'created_at': datetime.now().isoformat(),
            'status': 'stopped'
        }
        self.servers.append(server)
        self.save_servers()
        return server

    def update_server(self, server_id, name=None, bat_path=None, description=None, icon_path=None, stop_method=None,
                      display_cmd=None):
        """Обновление настроек сервера"""
        server = next((s for s in self.servers if s['id'] == server_id), None)
        if server:
            if name is not None:
                server['name'] = name
            if bat_path is not None:
                server['bat_path'] = bat_path
            if description is not None:
                server['description'] = description
            if icon_path is not None:
                server['icon_path'] = icon_path
            if stop_method is not None:
                server['stop_method'] = stop_method
            if display_cmd is not None:
                server['display_cmd'] = display_cmd

            self.save_servers()
            return True
        return False

    def remove_server(self, server_id):
        """Удаление сервера"""
        if server_id in self.processes:
            self.stop_server(server_id)

        self.servers = [s for s in self.servers if s['id'] != server_id]
        self.save_servers()
        return True

    def start_server(self, server_id):
        """Запуск сервера в отдельном окне командной строки"""
        server = next((s for s in self.servers if s['id'] == server_id), None)
        if server:
            try:
                bat_path = server['bat_path']
                server_dir = os.path.dirname(bat_path)

                # Запуск в отдельном окне командной строки
                process = subprocess.Popen(
                    ['cmd.exe', '/c', bat_path],
                    cwd=server_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )

                self.processes[server_id] = process.pid
                server['status'] = 'running'
                server['started_at'] = datetime.now().isoformat()
                self.save_servers()

                return True
            except Exception as e:
                print(f"Ошибка запуска: {e}")
                return False
        return False

    def stop_server(self, server_id):
        """Остановка сервера в зависимости от выбранного метода"""
        server = next((s for s in self.servers if s['id'] == server_id), None)
        if not server or server_id not in self.processes:
            return False

        try:
            pid = self.processes[server_id]
            process = psutil.Process(pid)

            if server['stop_method'] == 'stop_command':
                # Попытка отправить команду 'stop' в процесс
                success = self.send_stop_command(process)
                if not success:
                    # Если не удалось, принудительно закрываем
                    self.force_stop_process(process)
            else:
                # Просто закрываем CMD
                self.force_stop_process(process)

            # Обновляем статус
            del self.processes[server_id]
            server['status'] = 'stopped'
            self.save_servers()

            return True
        except Exception as e:
            print(f"Ошибка остановки: {e}")
            return False

    def send_stop_command(self, process):
        """Отправка команды 'stop' в процесс"""
        try:
            # Для Minecraft серверов команда 'stop' должна быть отправлена в консоль
            for child in process.children(recursive=True):
                try:
                    # Попытка отправить команду через stdin
                    if child.is_running():
                        # Здесь должна быть логика отправки команды в консоль сервера
                        pass
                except:
                    pass

            # Даем время на graceful shutdown
            import time
            time.sleep(5)

            # Проверяем, завершился ли процесс
            if not process.is_running():
                return True

            # Если процесс еще жив, принудительно завершаем
            self.force_stop_process(process)
            return True

        except Exception as e:
            print(f"Ошибка отправки команды stop: {e}")
            return False

    def force_stop_process(self, process):
        """Принудительная остановка процесса"""
        try:
            for child in process.children(recursive=True):
                child.terminate()
            process.terminate()
            process.wait(timeout=10)
        except:
            try:
                subprocess.run(['taskkill', '/f', '/pid', str(process.pid)])
            except:
                pass

    def get_system_info(self):
        """Получение информации о системе"""
        return {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'architecture': platform.architecture()[0],
            'processor': platform.processor(),
            'python_version': platform.python_version()
        }


# Создаем экземпляр менеджера
manager = ServerManager()


# Eel функции
@eel.expose
def get_servers():
    return manager.servers


@eel.expose
def add_server(name, bat_path, description, icon_path=None, stop_method='stop_command', display_cmd=False):
    return manager.add_server(name, bat_path, description, icon_path, stop_method, display_cmd)


@eel.expose
def update_server(server_id, name, bat_path, description, icon_path, stop_method, display_cmd):
    return manager.update_server(server_id, name, bat_path, description, icon_path, stop_method, display_cmd)


@eel.expose
def remove_server(server_id):
    return manager.remove_server(server_id)


@eel.expose
def start_server(server_id):
    return manager.start_server(server_id)


@eel.expose
def stop_server(server_id):
    return manager.stop_server(server_id)


@eel.expose
def get_server_info(server_id):
    server = next((s for s in manager.servers if s['id'] == server_id), None)
    if server:
        return {
            'server': server,
            'system_info': manager.get_system_info()
        }
    return None


@eel.expose
def get_app_version():
    return {
        'version': '1.0.0',
        'credits': '0vfx, deepseek'
    }


if __name__ == "__main__":
    print("Запуск менеджера серверов Minecraft...")
    print("Версия: 1.0.0")
    print("Разработчики: 0vfx, deepseek")
    eel.start('index.html', size=(1000, 700), mode='chrome', port=8000)