-- Django создаёт отдельную базу для тестов — пользователю приложения нужен доступ и к ней.
GRANT ALL PRIVILEGES ON `test_carsharing`.* TO 'carsharing'@'%';
FLUSH PRIVILEGES;
