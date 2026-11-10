<?php
/**
 * Прогноз погоды для «Индекса мойки» на главной.
 *
 * Источник — MET Norway (api.met.no): бесплатен и для коммерческих сайтов,
 * лицензия CC BY 4.0 — подпись источника выводится в самом виджете.
 * Их условия требуют представляться в User-Agent и не дёргать API на каждый
 * визит, поэтому ответ кэшируется на час, а браузеры посетителей ходят
 * только сюда: их IP к третьей стороне не уходят.
 *
 * Отдаёт сводку по дням в часовом поясе Минска:
 * {"days":[{"date":"2026-11-09","precip":1.4,"snow":false,"tmin":-1,"tmax":4}, ...]}
 */

declare(strict_types=1);

const LAT = 53.16;
const LON = 29.21;
const CACHE_TTL = 3600;
const DAYS = 6;
const USER_AGENT = 'lighton.by/1.0 lighton9871010@mail.ru';

header('Content-Type: application/json; charset=utf-8');

/**
 * Нет прогноза — пустой ответ, но с кодом 200: виджет на пустом списке сам
 * показывает общий совет, а ошибка 5xx светилась бы в консоли у каждого
 * посетителя (и снижала оценку Lighthouse), если хостинг запрещает PHP
 * исходящие запросы.
 */
function fail(): void
{
    header('Cache-Control: no-store');
    echo '{"days":[]}';
    exit;
}

/**
 * GET-запрос двумя способами: на части хостингов выключен allow_url_fopen,
 * но есть расширение curl, на других — наоборот. Причина неудачи пишется
 * в $error для страницы самодиагностики (?check=1).
 */
function httpGet(string $url, string &$error): ?string
{
    $error = '';

    if (ini_get('allow_url_fopen')) {
        $context = stream_context_create([
            'http' => ['header' => 'User-Agent: ' . USER_AGENT, 'timeout' => 8],
        ]);
        $raw = @file_get_contents($url, false, $context);
        if ($raw !== false) {
            return $raw;
        }
        $error = 'file_get_contents: ' . (error_get_last()['message'] ?? 'неизвестная ошибка');
    }

    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_USERAGENT => USER_AGENT,
            CURLOPT_TIMEOUT => 8,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_ENCODING => '',
        ]);
        $raw = curl_exec($ch);
        $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if ($raw !== false && $code === 200) {
            return $raw;
        }
        $error = trim($error . ' | curl: ' . (curl_error($ch) ?: "HTTP $code"), ' |');
    }

    if ($error === '') {
        $error = 'на хостинге выключены и allow_url_fopen, и расширение curl';
    }
    return null;
}

function fetchForecast(string &$error = ''): ?array
{
    // Переменная окружения — только для локальной проверки на тестовых данных;
    // посетитель сайта её задать не может.
    $fixture = getenv('LIGHTON_WEATHER_FIXTURE');
    if ($fixture) {
        $raw = @file_get_contents($fixture);
        $raw = $raw === false ? null : $raw;
    } else {
        $url = sprintf(
            'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=%.2f&lon=%.2f',
            LAT,
            LON
        );
        $raw = httpGet($url, $error);
    }

    if ($raw === null) {
        return null;
    }
    $data = json_decode($raw, true);
    return is_array($data) ? $data : null;
}

/** Сводит почасовой/шестичасовой ряд MET Norway в дни по минскому времени. */
function summarize(array $met): array
{
    $tz = new DateTimeZone('Europe/Minsk');
    $days = [];

    foreach ($met['properties']['timeseries'] ?? [] as $entry) {
        $date = (new DateTimeImmutable($entry['time']))->setTimezone($tz)->format('Y-m-d');
        $data = $entry['data'] ?? [];

        $day = $days[$date] ?? ['date' => $date, 'precip' => 0.0, 'snow' => false, 'tmin' => null, 'tmax' => null];

        $t = $data['instant']['details']['air_temperature'] ?? null;
        if (is_numeric($t)) {
            $day['tmin'] = $day['tmin'] === null ? $t : min($day['tmin'], $t);
            $day['tmax'] = $day['tmax'] === null ? $t : max($day['tmax'], $t);
        }

        // В первые ~2,5 суток ряд почасовой (есть next_1_hours), дальше — шаг
        // 6 часов. Берём один из периодов, иначе осадки посчитались бы дважды.
        $period = $data['next_1_hours'] ?? $data['next_6_hours'] ?? null;
        if ($period) {
            $day['precip'] += (float) ($period['details']['precipitation_amount'] ?? 0);
            $symbol = (string) ($period['summary']['symbol_code'] ?? '');
            if (strpos($symbol, 'snow') !== false || strpos($symbol, 'sleet') !== false) {
                $day['snow'] = true;
            }
        }

        $days[$date] = $day;
    }

    $out = [];
    foreach (array_slice(array_values($days), 0, DAYS) as $day) {
        if ($day['tmin'] === null) {
            continue;
        }
        $out[] = [
            'date' => $day['date'],
            'precip' => round($day['precip'], 1),
            'snow' => $day['snow'],
            'tmin' => (int) round($day['tmin']),
            'tmax' => (int) round($day['tmax']),
        ];
    }
    return $out;
}

/**
 * Кэш — рядом со скриптом, системный /tmp только запасной вариант: на
 * хостингах с open_basedir (ISPmanager и подобные) PHP часто запрещено
 * писать в /tmp. Прогноз не секретный, открытый файл в /api/ не страшен.
 */
function cacheFile(): string
{
    foreach ([__DIR__, sys_get_temp_dir()] as $dir) {
        if (@is_writable($dir)) {
            return $dir . '/lighton_weather.json';
        }
    }
    return '';
}

$cacheFile = cacheFile();
$cacheAge = ($cacheFile !== '' && @is_file($cacheFile)) ? time() - (int) filemtime($cacheFile) : null;
$check = isset($_GET['check']);

// В режиме проверки идём к источнику заново, но не чаще раза в минуту —
// чтобы ссылку проверки нельзя было использовать для засыпания MET запросами.
$needFetch = $cacheAge === null || $cacheAge >= CACHE_TTL || ($check && $cacheAge >= 60);

$payload = null;
$error = '';
$fetchedOk = false;

if ($needFetch) {
    $met = fetchForecast($error);
    $days = $met ? summarize($met) : [];
    if ($days) {
        $fetchedOk = true;
        $payload = json_encode(['days' => $days]);
        // Не записался кэш — не беда: свежий прогноз всё равно отдаём.
        if ($cacheFile !== '') {
            @file_put_contents($cacheFile, $payload, LOCK_EX);
        }
    } elseif ($met && $error === '') {
        $error = 'источник ответил, но данных прогноза в ответе нет';
    }
}

// Если источник недоступен — лучше вчерашний прогноз, чем пустой виджет.
if ($payload === null && $cacheAge !== null) {
    $payload = @file_get_contents($cacheFile) ?: null;
}

if ($check) {
    // Самодиагностика: https://lighton.by/api/weather.php?check=1
    header('Cache-Control: no-store');
    $days = $payload ? (json_decode($payload, true)['days'] ?? []) : [];
    echo json_encode([
        'итог' => $days ? 'Прогноз есть — виджет будет работать' : 'Прогноза нет — виджет покажет общий совет',
        'запрос к MET Norway' => $needFetch
            ? ($fetchedOk ? 'успешно' : 'ошибка: ' . $error)
            : 'не делался — свежий кэш, возраст ' . intdiv((int) $cacheAge, 60) . ' мин',
        'allow_url_fopen' => (bool) ini_get('allow_url_fopen'),
        'curl' => function_exists('curl_init'),
        'кэш' => $cacheFile !== '' ? $cacheFile : 'нет папки, доступной для записи',
        'PHP' => PHP_VERSION,
        'дней в прогнозе' => count($days),
        'сегодня' => $days[0] ?? null,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($payload === null) {
    fail();
}

header('Cache-Control: public, max-age=1800');
echo $payload;
