# Основное задание:

1. Account URL: http://localhost:5001
2. Hospital URL: http://localhost:5002
3. Timetable URL: http://localhost:5003
4. Document URL: http://localhost:5004

# Дополнительная информация

## Проблема: Ошибка подключения к PostgreSQL

Если при запуске проекта вы видите ошибку вида:

```
psycopg2.OperationalError: FATAL: no pg_hba.conf entry for host "xxx.xxx.xxx.xxx", user "user", database "your_db", no encryption
```

Эта ошибка возникает, когда PostgreSQL не разрешает подключение к базе данных с текущего IP-адреса. Для исправления этой проблемы выполните следующие шаги.

## Шаги для исправления

### 1. Подключение к контейнеру PostgreSQL

Для начала подключитесь к контейнеру с PostgreSQL. Выполните следующую команду:

```bash
docker exec -it <container_id> bash
```

Замените `<container_id>` на ID контейнера с PostgreSQL. Чтобы узнать ID контейнера, используйте команду:

```bash
docker ps
```

### 2. Открытие файла конфигурации `pg_hba.conf`

После подключения к контейнеру необходимо отредактировать файл конфигурации `pg_hba.conf`. Для этого откройте файл с помощью текстового редактора (например, `nano`):

```bash
nano /var/lib/postgresql/data/pg_hba.conf
```

### 3. Изменение настроек

Найдите и измените строку, отвечающую за аутентификацию, чтобы разрешить подключения для всех IP-адресов (например, добавьте следующую строку в конце файла):

```plaintext
host    all             all             0.0.0.0/0               md5
```

### 4. Перезапуск контейнера PostgreSQL

После внесения изменений перезапустите контейнер с PostgreSQL:

```bash
docker-compose restart db
```

После выполнения этих шагов проблема с подключением к базе данных должна быть решена.
```