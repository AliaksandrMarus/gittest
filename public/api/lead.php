<?php
/**
 * Приём заявок с форм сайта.
 *
 * Куда класть: рядом с собранным сайтом, по адресу /api/lead.php.
 * Требуется PHP 7.4+ и работающая функция mail() либо SMTP на хостинге.
 *
 * Настройки — в соседнем файле config.local.php (см. config.local.php.example).
 * Он не попадает в репозиторий, поэтому токен Telegram не утекает ни в git,
 * ни в код страницы.
 */

declare(strict_types=1);

const MAIL_TO_DEFAULT = 'lighton9871010@mail.ru';
const MIN_FILL_MS = 3000;
const RATE_LIMIT_SECONDS = 30;

$config = [
    'mail_to'           => MAIL_TO_DEFAULT,
    'mail_from'         => 'noreply@lighton.by',
    'telegram_token'    => '',
    'telegram_chat_id'  => '',
];

if (is_file(__DIR__ . '/config.local.php')) {
    $local = require __DIR__ . '/config.local.php';
    if (is_array($local)) {
        $config = array_merge($config, $local);
    }
}

/** Отдаёт ответ и завершает работу. */
function respond(int $code, string $message): void
{
    http_response_code($code);
    $wantsJson = stripos($_SERVER['HTTP_ACCEPT'] ?? '', 'application/json') !== false;

    if ($wantsJson) {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(
            ['ok' => $code < 400, 'message' => $message],
            JSON_UNESCAPED_UNICODE
        );
        exit;
    }

    // Запасной путь для браузера без JS: обычная страница с результатом.
    header('Content-Type: text/html; charset=utf-8');
    $safe = htmlspecialchars($message, ENT_QUOTES, 'UTF-8');
    echo "<!doctype html><html lang=\"ru\"><meta charset=\"utf-8\">"
       . "<title>Заявка</title>"
       . "<body style=\"font:16px/1.6 system-ui;background:#0a0c10;color:#eef2f7;"
       . "display:grid;place-items:center;min-height:100vh;margin:0;text-align:center;padding:2rem\">"
       . "<div><p>{$safe}</p><p><a href=\"/\" style=\"color:#5ee7ff\">Вернуться на сайт</a></p></div>";
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    respond(405, 'Метод не поддерживается.');
}

// Простое ограничение частоты по IP: вторая заявка за 30 секунд отклоняется.
$ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$lockFile = sys_get_temp_dir() . '/lighton_lead_' . md5($ip);
if (is_file($lockFile) && (time() - (int) filemtime($lockFile)) < RATE_LIMIT_SECONDS) {
    respond(429, 'Заявка уже отправлена. Если это срочно — позвоните: +375 25 987-10-10.');
}

$field = static function (string $key, int $max = 200): string {
    $raw = $_POST[$key] ?? '';
    if (!is_string($raw)) {
        return '';
    }
    // Переводы строк вычищаем — иначе в заголовки письма можно подставить своё.
    $clean = str_replace(["\r", "\n", "\0"], ' ', trim($raw));
    return mb_substr($clean, 0, $max);
};

// Ловушка для ботов: поле спрятано от людей, значит заполнить его мог только скрипт.
if ($field('company') !== '') {
    respond(200, 'Спасибо, заявка принята.');
}

$startedAt = (int) ($_POST['ts'] ?? 0);
if ($startedAt > 0 && (microtime(true) * 1000 - $startedAt) < MIN_FILL_MS) {
    respond(400, 'Форма заполнена подозрительно быстро. Попробуйте ещё раз.');
}

$name    = $field('name', 60);
$phone   = $field('phone', 30);
$service = $field('service', 120);
$when    = $field('when', 60);
$car     = $field('car', 80);
$comment = $field('comment', 600);
$page    = $field('page', 200);
$variant = $field('variant', 20);

if (mb_strlen($name) < 2) {
    respond(400, 'Укажите, как к вам обращаться.');
}

if (empty($_POST['consent'])) {
    respond(400, 'Нужно согласие на обработку персональных данных.');
}

// Номер приводим к 9 значащим цифрам и проверяем код оператора.
$digits = preg_replace('/\D+/', '', $phone) ?? '';
if (str_starts_with($digits, '375')) {
    $digits = substr($digits, 3);
} elseif (str_starts_with($digits, '80')) {
    $digits = substr($digits, 2);
}

if (strlen($digits) !== 9 || !in_array(substr($digits, 0, 2), ['25', '29', '33', '44'], true)) {
    respond(400, 'Проверьте номер телефона: нужен белорусский мобильный.');
}

$phonePretty = sprintf(
    '+375 (%s) %s-%s-%s',
    substr($digits, 0, 2),
    substr($digits, 2, 3),
    substr($digits, 5, 2),
    substr($digits, 7, 2)
);

$kind = match ($variant) {
    'callback' => 'Обратный звонок',
    'calc'     => 'Расчёт стоимости',
    default    => 'Запись на услугу',
};

$rows = array_filter([
    'Тип'         => $kind,
    'Имя'         => $name,
    'Телефон'     => $phonePretty,
    'Услуга'      => $service,
    'Автомобиль'  => $car,
    'Когда'       => $when,
    'Комментарий' => $comment,
    'Страница'    => $page,
    'Время'       => date('d.m.Y H:i'),
], static fn ($v) => $v !== '');

$lines = [];
foreach ($rows as $label => $value) {
    $lines[] = "{$label}: {$value}";
}
$body = implode("\n", $lines);

$delivered = false;

// 1. Письмо на почту.
$subject = "Заявка с сайта: {$kind} — {$phonePretty}";
$headers = implode("\r\n", [
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'From: Lighton <' . $config['mail_from'] . '>',
    'Reply-To: ' . $config['mail_from'],
    'X-Mailer: PHP/' . phpversion(),
]);

if (@mail($config['mail_to'], '=?UTF-8?B?' . base64_encode($subject) . '?=', $body, $headers)) {
    $delivered = true;
}

// 2. Дубль в Telegram, если настроен. Токен читается только на сервере.
if ($config['telegram_token'] !== '' && $config['telegram_chat_id'] !== '') {
    $payload = http_build_query([
        'chat_id' => $config['telegram_chat_id'],
        'text'    => "🚗 Новая заявка\n\n{$body}",
    ]);

    $ch = curl_init("https://api.telegram.org/bot{$config['telegram_token']}/sendMessage");
    if ($ch !== false) {
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 5,
        ]);
        $result = curl_exec($ch);
        $status = curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        curl_close($ch);
        if ($result !== false && $status === 200) {
            $delivered = true;
        }
    }
}

if (!$delivered) {
    // Заявку всё равно сохраняем: потерять клиента из-за сбоя почты нельзя.
    @file_put_contents(
        __DIR__ . '/leads.log',
        date('c') . ' ' . str_replace("\n", ' | ', $body) . PHP_EOL,
        FILE_APPEND | LOCK_EX
    );
    respond(500, 'Не удалось отправить заявку. Позвоните, пожалуйста: +375 25 987-10-10.');
}

@touch($lockFile);
respond(200, 'Заявка принята. Перезвоним в рабочее время — Пн–Сб с 09:00 до 19:00.');
