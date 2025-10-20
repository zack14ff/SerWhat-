import eel
import json
import os
import subprocess
import psutil
import platform
import threading
import time
from datetime import datetime
from os.path import abspath, exists

# Инициализация Eel
eel.init(abspath('web'))


class ServerManager:
    def __init__(self):
        self.servers_file = 'servers.json'
        self.settings_file = 'app_settings.json'
        self.servers = self.load_servers()
        self.processes = {}
        self.process_checker_running = True
        self.start_process_checker()
        print("ServerManager инициализирован")

    def start_process_checker(self):
        """Запуск фоновой проверки процессов"""

        def checker():
            while self.process_checker_running:
                try:
                    self.check_processes_status()
                    time.sleep(3)
                except Exception as e:
                    print(f"Ошибка в проверке процессов: {e}")

        thread = threading.Thread(target=checker, daemon=True)
        thread.start()

    def check_processes_status(self):
        """Проверка статуса всех процессов"""
        for server_id, pid in list(self.processes.items()):
            try:
                process = psutil.Process(pid)
                if not process.is_running():
                    del self.processes[server_id]
                    server = next((s for s in self.servers if s['id'] == server_id), None)
                    if server and server['status'] == 'running':
                        server['status'] = 'stopped'
                        self.save_servers()
                        print(f"Сервер {server_id} завершен")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                if server_id in self.processes:
                    del self.processes[server_id]
                    server = next((s for s in self.servers if s['id'] == server_id), None)
                    if server and server['status'] == 'running':
                        server['status'] = 'stopped'
                        self.save_servers()

    def load_servers(self):
        """Загрузка серверов из JSON файла"""
        if os.path.exists(self.servers_file):
            try:
                with open(self.servers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for server in data:
                        if 'stop_method' not in server:
                            server['stop_method'] = 'stop_command'
                        if 'display_cmd' not in server:
                            server['display_cmd'] = False
                        if 'icon_position' not in server:
                            server['icon_position'] = 'left'
                        if 'server_ip' not in server:
                            server['server_ip'] = 'localhost'
                        if 'server_port' not in server:
                            server['server_port'] = '25565'
                    print(f"Загружено {len(data)} серверов")
                    return data
            except Exception as e:
                print(f"Ошибка загрузки серверов: {e}")
                return []
        print("Файл серверов не найден, создаем новый")
        return []

    def save_servers(self):
        """Сохранение серверов в JSON файл"""
        try:
            with open(self.servers_file, 'w', encoding='utf-8') as f:
                json.dump(self.servers, f, ensure_ascii=False, indent=2)
            print("Серверы сохранены")
        except Exception as e:
            print(f"Ошибка сохранения серверов: {e}")

    def get_app_settings(self):
        """Получение настроек приложения"""
        default_settings = {
            'language': 'ru',
            'theme': 'dark'
        }

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return {**default_settings, **json.load(f)}
            except:
                return default_settings
        return default_settings

    def save_app_settings(self, settings):
        """Сохранение настроек приложения"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            print("Настройки приложения сохранены")
            return True
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
            return False

    def add_server(self, name, bat_path, description, icon_path=None, stop_method='stop_command', display_cmd=False,
                   icon_position='left', server_ip='localhost', server_port='25565'):
        """Добавление нового сервера"""
        try:
            print(f"Добавление сервера: {name}, {bat_path}")

            # Проверяем обязательные поля
            if not name or not bat_path:
                return {'success': False, 'error': 'Заполните название и путь к BAT файлу'}

            server_id = len(self.servers) + 1
            server = {
                'id': server_id,
                'name': name,
                'bat_path': bat_path,
                'description': description,
                'icon_path': icon_path,
                'stop_method': stop_method,
                'display_cmd': display_cmd,
                'icon_position': icon_position,
                'server_ip': server_ip,
                'server_port': server_port,
                'created_at': datetime.now().isoformat(),
                'status': 'stopped'
            }

            self.servers.append(server)
            self.save_servers()

            print(f"Сервер успешно добавлен с ID: {server_id}")
            return {'success': True, 'server': server}

        except Exception as e:
            print(f"Ошибка при добавлении сервера: {e}")
            return {'success': False, 'error': str(e)}

    def update_server(self, server_id, name=None, bat_path=None, description=None, icon_path=None, stop_method=None,
                      display_cmd=None, icon_position=None, server_ip=None, server_port=None):
        """Обновление настроек сервера"""
        try:
            server = next((s for s in self.servers if s['id'] == server_id), None)
            if not server:
                return False

            updates = []
            if name is not None and server['name'] != name:
                server['name'] = name
                updates.append('name')
            if bat_path is not None and server['bat_path'] != bat_path:
                server['bat_path'] = bat_path
                updates.append('bat_path')
            if description is not None and server['description'] != description:
                server['description'] = description
                updates.append('description')
            if icon_path is not None and server['icon_path'] != icon_path:
                server['icon_path'] = icon_path
                updates.append('icon_path')
            if stop_method is not None and server['stop_method'] != stop_method:
                server['stop_method'] = stop_method
                updates.append('stop_method')
            if display_cmd is not None and server['display_cmd'] != display_cmd:
                server['display_cmd'] = display_cmd
                updates.append('display_cmd')
            if icon_position is not None and server['icon_position'] != icon_position:
                server['icon_position'] = icon_position
                updates.append('icon_position')
            if server_ip is not None and server['server_ip'] != server_ip:
                server['server_ip'] = server_ip
                updates.append('server_ip')
            if server_port is not None and server['server_port'] != server_port:
                server['server_port'] = server_port
                updates.append('server_port')

            if updates:
                self.save_servers()
                print(f"Сервер {server_id} обновлен: {', '.join(updates)}")

            return True

        except Exception as e:
            print(f"Ошибка обновления сервера: {e}")
            return False

    def remove_server(self, server_id):
        """Удаление сервера"""
        try:
            if server_id in self.processes:
                self.stop_server(server_id)

            initial_count = len(self.servers)
            self.servers = [s for s in self.servers if s['id'] != server_id]

            if len(self.servers) < initial_count:
                self.save_servers()
                print(f"Сервер {server_id} удален")
                return True
            else:
                print(f"Сервер {server_id} не найден для удаления")
                return False

        except Exception as e:
            print(f"Ошибка удаления сервера: {e}")
            return False

    def start_server(self, server_id):
        """Запуск сервера в отдельном окне командной строки"""
        try:
            server = next((s for s in self.servers if s['id'] == server_id), None)
            if not server:
                return {'success': False, 'error': 'Сервер не найден'}

            bat_path = server['bat_path']

            if not exists(bat_path):
                return {'success': False, 'error': f'BAT файл не найден: {bat_path}'}

            server_dir = os.path.dirname(bat_path) or os.getcwd()

            print(f"Запуск сервера {server_id}: {bat_path} в {server_dir}")

            process = subprocess.Popen(
                ['cmd.exe', '/c', bat_path],
                cwd=server_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )

            self.processes[server_id] = process.pid
            server['status'] = 'running'
            server['started_at'] = datetime.now().isoformat()
            self.save_servers()

            print(f"Сервер {server_id} запущен с PID: {process.pid}")
            return {'success': True}

        except Exception as e:
            print(f"Ошибка запуска сервера: {e}")
            return {'success': False, 'error': str(e)}

    def stop_server(self, server_id):
        """Остановка сервера"""
        try:
            server = next((s for s in self.servers if s['id'] == server_id), None)
            if not server or server_id not in self.processes:
                return {'success': False, 'error': 'Сервер не запущен'}

            pid = self.processes[server_id]
            print(f"Остановка сервера {server_id} (PID: {pid}) методом: {server['stop_method']}")

            if server['stop_method'] == 'stop_command':
                time.sleep(2)  # Даем время для graceful shutdown
            else:
                # Принудительное закрытие
                try:
                    subprocess.run(['taskkill', '/f', '/pid', str(pid)], check=True, timeout=10)
                except:
                    try:
                        process = psutil.Process(pid)
                        process.terminate()
                        process.wait(timeout=5)
                    except:
                        pass

            if server_id in self.processes:
                del self.processes[server_id]

            server['status'] = 'stopped'
            self.save_servers()

            print(f"Сервер {server_id} остановлен")
            return {'success': True}

        except Exception as e:
            print(f"Ошибка остановки сервера: {e}")
            return {'success': False, 'error': str(e)}

    def select_file_dialog(self, file_type="bat"):
        """Диалог выбора файла"""
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)

            if file_type == "bat":
                file_path = filedialog.askopenfilename(
                    title="Выберите .bat файл сервера",
                    filetypes=[("Batch files", "*.bat"), ("All files", "*.*")]
                )
            else:
                file_path = filedialog.askopenfilename(
                    title="Выберите файл иконки",
                    filetypes=[("Image files", "*.png *.jpg *.jpeg *.ico *.bmp"), ("All files", "*.*")]
                )

            root.destroy()
            print(f"Выбран файл: {file_path}")
            return file_path

        except Exception as e:
            print(f"Ошибка диалога выбора файла: {e}")
            return ""

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
    print("Запрос списка серверов")
    return manager.servers


@eel.expose
def add_server(name, bat_path, description, icon_path=None, stop_method='stop_command', display_cmd=False,
               icon_position='left', server_ip='localhost', server_port='25565'):
    print(f"Вызов add_server: {name}, {bat_path}")
    return manager.add_server(name, bat_path, description, icon_path, stop_method, display_cmd, icon_position,
                              server_ip, server_port)


@eel.expose
def update_server(server_id, name, bat_path, description, icon_path, stop_method, display_cmd, icon_position, server_ip,
                  server_port):
    print(f"Вызов update_server для сервера {server_id}")
    return manager.update_server(server_id, name, bat_path, description, icon_path, stop_method, display_cmd,
                                 icon_position, server_ip, server_port)


@eel.expose
def remove_server(server_id):
    print(f"Вызов remove_server для сервера {server_id}")
    return manager.remove_server(server_id)


@eel.expose
def start_server(server_id):
    print(f"Вызов start_server для сервера {server_id}")
    return manager.start_server(server_id)


@eel.expose
def stop_server(server_id):
    print(f"Вызов stop_server для сервера {server_id}")
    return manager.stop_server(server_id)


@eel.expose
def select_file(file_type):
    print(f"Вызов select_file для типа: {file_type}")
    return manager.select_file_dialog(file_type)


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
def get_app_settings():
    return manager.get_app_settings()


@eel.expose
def save_app_settings(settings):
    return manager.save_app_settings(settings)


@eel.expose
def get_app_version():
    return {
        'version': '1.2.0',
        'credits': '0vfx, deepseek'
    }


if __name__ == "__main__":
    print("=" * 50)
    print("Запуск менеджера серверов Minecraft v1.2.0")
    print("Разработчики: 0vfx, deepseek")
    print("=" * 50)

    try:
        eel.start('index.html', size=(1000, 700), mode='chrome', port=8000)
    except Exception as e:
        print(f"Ошибка запуска: {e}")
    finally:
        manager.process_checker_running = False
        print("Приложение завершено")
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
