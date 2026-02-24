#!/bin/bash
# Один раз на сервере: открыть порт 8080 для доступа из LAN
# Запуск: sudo bash scripts/setup-firewall.sh

if systemctl is-active firewalld >/dev/null 2>&1; then
    echo "Добавляю порт 8080 в firewalld..."
    firewall-cmd --add-port=8080/tcp --permanent
    firewall-cmd --reload
    echo "Готово."
else
    echo "firewalld не запущен — порт уже доступен."
fi
