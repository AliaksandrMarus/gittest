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

function fail(): void
{
    http_response_code(503);
    echo '{"days":[]}';
    exit;
}

function fetchForecast(): ?array
{
    // Переменная окружения — только для локальной проверки на тестовых данных;
    // посетитель сайта её задать не может.
    $fixture = getenv('LIGHTON_WEATHER_FIXTURE');
    if ($fixture) {
        $raw = @file_get_contents($fixture);
    } else {
        $url = sprintf(
            'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=%.2f&lon=%.2f',
            LAT,
            LON
        );
        $context = stream_context_create([
            'http' => ['header' => 'User-Agent: ' . USER_AGENT, 'timeout' => 8],
        ]);
        $raw = @file_get_contents($url, false, $context);
    }

    if ($raw === false) {
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

$cacheFile = sys_get_temp_dir() . '/lighton_weather.json';
$cacheFresh = is_file($cacheFile) && (time() - (int) filemtime($cacheFile)) < CACHE_TTL;

if (!$cacheFresh) {
    $met = fetchForecast();
    $days = $met ? summarize($met) : [];
    if ($days) {
        @file_put_contents($cacheFile, json_encode(['days' => $days]), LOCK_EX);
    }
}

// Если источник недоступен — лучше вчерашний прогноз, чем пустой виджет.
$cached = is_file($cacheFile) ? file_get_contents($cacheFile) : false;
if ($cached === false) {
    fail();
}

header('Cache-Control: public, max-age=1800');
echo $cached;
