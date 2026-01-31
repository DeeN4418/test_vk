import os
import time
import winreg
import re
from datetime import datetime
import threading

class SteamDownloadMonitor:
    def __init__(self):
        self.steam_path = self.get_steam_path()
        self.log_file = None
        self.current_game = "Unknown"
        self.download_speeds = []
        self.is_downloading = False
        
    def get_steam_path(self): # получаем путь к Steam из реестра
        try:            
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 r"Software\Valve\Steam")
            steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
            winreg.CloseKey(key)
            
            if os.path.exists(steam_path):
                print(f"Steam найден: {steam_path}")
                return steam_path
            else:
                print("Steam не найден")
                return None
                
        except Exception as e:
            print(f"Не удалось получить путь к Steam из реестра: {e}")
            
                
    def find_log_file(self): # поиск актуального лог-файла Steam
        if not self.steam_path:
            return None
        
        logs_dir = os.path.join(self.steam_path, "logs")
        
        if not os.path.exists(logs_dir):
            print(f"Директория с логами не найдена: {logs_dir}")
            return None
        
        # поиск файлов с префиксом content_log
        log_files = []
        for file in os.listdir(logs_dir):
            if file.startswith("content_log") and file.endswith(".txt"):
                log_files.append(os.path.join(logs_dir, file))
        
        if not log_files:
            print("Лог-файлы не найдены")
            return None
        
        latest_log = max(log_files, key=os.path.getmtime) # определяем самый свежий файл
        return latest_log
    
    def parse_log_line(self, line): # парсинг строки лога для извлечения информации о загрузке
        try:
            # паттерн для скорости загрузки
            speed_pattern = r'(\d+\.\d+)\s*(?:[KM]?B/s)'
            speed_match = re.search(speed_pattern, line)
            
            # паттерн для названия игры
            game_pattern = r'Downloading\s+(.*?)\s+\((\d+)\s+of\s+\d+\)'
            game_match = re.search(game_pattern, line)
            
            # паттерн для статуса паузы
            pause_pattern = r'paused|Paused'
            is_paused = re.search(pause_pattern, line) is not None
            
            # паттерн для завершения загрузки
            complete_pattern = r'fully installed|download complete'
            is_complete = re.search(complete_pattern, line) is not None
            
            result = {
                'speed': None,
                'game': None,
                'is_paused': is_paused,
                'is_complete': is_complete,
                'raw_line': line.strip()
            }
            
            if speed_match:
                result['speed'] = float(speed_match.group(1))
            
            if game_match:
                result['game'] = game_match.group(1)
            
            return result
            
        except Exception as e:
            print(f"Ошибка при парсинге строки: {e}")
            return None
    
    def monitor_log_file(self, duration_minutes=5, interval_seconds=60): # основной метод мониторинга
        print("Запуск мониторинга загрузок Steam")
        print("=" * 50)
        
        # находим лог-файл
        self.log_file = self.find_log_file()
        if not self.log_file:
            print("Не удалось найти лог-файл Steam")
            return
        
        # читаем текущую позицию в файле
        last_position = os.path.getsize(self.log_file)
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        monitoring_interval = 1  # проверка лога каждую секунду
        output_counter = 0
        
        while time.time() < end_time and output_counter < duration_minutes:
            try:
                # открываем файл и переходим к последней позиции
                with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_position)
                    new_lines = f.readlines()
                    last_position = f.tell()
                
                # обрабатываем новые строки
                for line in new_lines:
                    parsed = self.parse_log_line(line)
                    if parsed:
                        if parsed['game']:
                            self.current_game = parsed['game']
                        
                        if parsed['speed']:
                            self.download_speeds.append(parsed['speed'])
                            self.is_downloading = True
                        
                        if parsed['is_paused']:
                            self.is_downloading = False
                        
                        if parsed['is_complete']:
                            self.is_downloading = False
                
                # Выводим статистику каждую минуту
                current_time = time.time()
                if current_time - start_time >= output_counter * interval_seconds:
                    self.print_status(output_counter + 1)
                    output_counter += 1
                
                time.sleep(monitoring_interval)
                
            except Exception as e:
                print(f"Ошибка при чтении лога: {e}")
                time.sleep(5)
        
        print("=" * 50)
        print("Мониторинг завершен")
        
    def print_status(self, minute_number): # вывод текущего статуса
        current_time = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n Статус на {current_time} (минута {minute_number}):")
        print(f"Игра: {self.current_game}")
        
        if self.is_downloading and self.download_speeds:
            avg_speed = sum(self.download_speeds[-10:]) / len(self.download_speeds[-10:])
            print(f"Скорость загрузки: {avg_speed:.2f} KB/s")
            print("Статус: Скачивается")
        else:
            print("Скорость загрузки: 0 KB/s")
            print("Статус: На паузе или не скачивается")
        
        print("-" * 30)
    
    def start_monitoring(self): # запуск мониторинга в отдельном потоке
        monitor_thread = threading.Thread(
            target=self.monitor_log_file,
            args=(5, 60)  # 5 минут, интервал 60 секунд
        )
        monitor_thread.daemon = True
        monitor_thread.start()
        return monitor_thread


def main(): # главная функция
        
    monitor = SteamDownloadMonitor() # создание и запуск монитора
    
    if monitor.steam_path:
        print("Начинаем мониторинг на 5 минут... \n")
        print("Для остановки нажмите Ctrl+C")
        
        try:
            monitor_thread = monitor.start_monitoring()
            monitor_thread.join()  
        except KeyboardInterrupt:
            print("\n\n Мониторинг остановлен пользователем")
    else:
        print(" Не удалось инициализировать монитор")

if __name__ == "__main__":
    main()