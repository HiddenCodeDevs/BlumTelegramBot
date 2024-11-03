[![Static Badge](https://img.shields.io/badge/Hidden_Code_LINKS-yes?style=for-the-badge&color=black)](https://t.me/hidden_coding)
[![Static Badge](https://img.shields.io/badge/Channel-yes?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/hidden_coding)
[![Static Badge](https://img.shields.io/badge/Chat-yes?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/hidden_codding_chat)
[![Static Badge](https://img.shields.io/badge/BOT_MARKET-yes?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/hcmarket_bot?start=referral_593084007)

# Сервер полезной нагрузки.

Для чего он нужен? В связи с обновлениями Blum, был изменен алгоритм подтверждение результата игры.
Для того чтобы закончить игру, требуется рассчитать сложное значение полезной нагрузки, алгоритм которого простым
способом невозможно перенести в бот. Однако разработчик **[sanjithacks](https://github.com/sanjithacks)** смог
извлечь из приложения игры генератор, выложив свои результаты в репозитории **[flower-signer](https://github.com/sanjithacks/flower-signer)**. 
Другой разработчик **[Arthur Koba](https://github.com/ArthurKoba)** использовал эти наработки и создал на их основе **[сервер генерации полезной нагрузки](https://github.com/KobaProduction/BlumPayloadGenerator)**,
который можно развернуть и запустить, а использовать его будет возможно на любом языке программирования за счет их взаимодействия по REST API.

# Информация по использованию

1. Вам необходимо установить Node.js (или обновить, требуется версия 20 и выше).
2. Установить [Сервер генерации полезной нагрузки](https://github.com/KobaProduction/BlumPayloadGenerator).
3. Запустить его и не закрывать! Он должен работать постоянно и одновременно с ботом.
   ###### **Если вы не знаете как это сделать - не пишите мне (_Arthur Koba_) в сообщения и не открывайте проблемы в репозитории.**
   ###### **Эта проблема не разработчиков, а сугубо лично ваша. Разбирайтесь самостоятельно или пишите в [чат Hidden Code](https://t.me/hidden_codding_chat/16053)**

# Особенности и почему так было сделано.

1. Бот можно использовать локально, нет зависимости от других серверов. Ранее бот играл в игры, получая полезную нагрузку с внешних сервера,
   однако их владелец потребовал оплаты за это, тем самым сломал работоспособность бота. Чтобы таких ситуаций не было,
   генератор можно использовать локально и никому ничего платить не нужно.
2. У вас есть также возможность развернуть сервер полезной нагрузки на хостинге, а в боте указать его внешний адрес. 
   Бот будет работать и в этом случае. Как это делать? Опять же, разбирайтесь или найдите человека который вам поможет.
3. Совместимость бота с иными серверами не предусмотрена, этот вопрос не обсуждается.


