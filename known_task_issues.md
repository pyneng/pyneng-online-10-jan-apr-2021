## Проблемы/нюансы с заданиями

### В задании 7.3a сортировка нужна "стандартная"

Сортировать надо sorted или sort. Их особенность в том, что они сортируют по первому
элементу, а если первый одинаковый, то по второму:

```python
In [1]: data = [[1, 100, 1000], [2, 2, 2], [1, 2, 3], [4, 100, 3]]

In [2]: sorted(data)
Out[2]: [[1, 2, 3], [1, 100, 1000], [2, 2, 2], [4, 100, 3]]
```

### В задании 7.3b не нужна сортировка

Я там так написала тест, что он ждет вывод по 10 влану в определенном порядке,
поэтому когда вывод отсортирован (из предыдущего задания), тест не проходит.

> это недочет именно теста


### Тест в задании 18.2a не подчищает `\r\n`

Если в задании 18.2a использовать не просто send_config_set, а отдельно выходить
заходить в конфиг режим, в вывод попадают `\r\n` вместо `\n`  и тест не проходит.

Надо отправить команды send_config_set без выхода/захода в конфиг режим отдельными
методами.


### Тест в задании 17.3b сам удаляет дубли

Тест в задании 17.3b сам удаляет дубли, поэтому тест проходит даже если функция работает
неправильно.
