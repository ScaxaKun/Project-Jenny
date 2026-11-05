/* =====================================================================
   SIMOCS - fungsi bersama untuk menentukan status data kamera
   Dipakai oleh halaman Dashboard dan Monitoring.
   ===================================================================== */
(function (global) {

    // ============ PENGATURAN ============
    // Sesuaikan dengan seberapa sering AI Engine mengirim data.
    // Contoh: kalau AI Engine mengirim tiap 10 detik, 60 detik tanpa data sudah patut dicurigai.
    var DELAYED_AFTER_SEC = 60;    // data lebih lama dari ini  -> "Delayed"
    var OFFLINE_AFTER_SEC = 300;   // data lebih lama dari ini  -> "Offline"

    // Peringatan "terlalu lama": duduk atau berdiri terus-menerus selama ini atau lebih.
    // Dihitung dari durasi yang dikirim AI Engine. Jalan kaki (walking) tidak pernah jadi peringatan.
    var ALERT_AFTER_SEC = 3600;                        // 1 jam
    var ALERT_ACTIVITIES = ['sitting', 'standing'];    // aktivitas yang bisa jadi peringatan
    // ====================================

    var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    function pad(n) { return (n < 10 ? '0' : '') + n; }

    // "2026-09-29 14:30:15" -> Date (dibaca sebagai waktu lokal)
    function parseTimestamp(str) {
        if (!str) return null;
        var m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/.exec(String(str));
        if (!m) return null;
        return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
    }

    // Date -> "29 Sep 2026, 14:30:15"
    function formatDateTime(d) {
        return d.getDate() + ' ' + MONTHS[d.getMonth()] + ' ' + d.getFullYear() + ', ' +
               pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    }

    function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }
    function people(n) { return n + (n === 1 ? ' person' : ' people'); }

    // 45 -> "45 s"; 312 -> "5 min 12 s"; 3725 -> "1 h 2 min"
    function formatLongDuration(sec) {
        sec = Math.max(0, Math.round(Number(sec) || 0));
        if (sec < 60) return sec + ' s';
        if (sec < 3600) {
            var m = Math.floor(sec / 60), r = sec % 60;
            return m + ' min' + (r ? ' ' + r + ' s' : '');
        }
        var h = Math.floor(sec / 3600), mm = Math.floor((sec % 3600) / 60);
        return h + ' h' + (mm ? ' ' + mm + ' min' : '');
    }

    // Satu aktivitas (person_id, activity, duration) termasuk peringatan?
    function isAlert(act) {
        var name = String((act && act.activity) || '').toLowerCase();
        return ALERT_ACTIVITIES.indexOf(name) !== -1 && Number(act.duration) >= ALERT_AFTER_SEC;
    }

    // Nama aktivitas -> nama class label warna
    function activityClass(name) {
        name = String(name || '').toLowerCase();
        if (name === 'standing') return 'badge-standing';
        if (name === 'sitting') return 'badge-sitting';
        if (name === 'walking') return 'badge-walking';
        return 'badge-default';
    }

    // 125 -> "2 min"; 40 -> "40 s"; 9 hari -> "9 days"
    function formatDuration(sec) {
        if (sec < 60) return sec + ' s';
        if (sec < 3600) return Math.floor(sec / 60) + ' min';
        if (sec < 86400) return plural(Math.floor(sec / 3600), 'hour');
        return plural(Math.floor(sec / 86400), 'day');
    }

    // Hasil: { state, label, age, duration, ageText, date }
    //   state: 'online' | 'delayed' | 'offline' | 'nodata'
    function freshness(timestampStr) {
        var date = parseTimestamp(timestampStr);
        if (!date) {
            return { state: 'nodata', label: 'No data', age: null, duration: '', ageText: '', date: null };
        }
        var age = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
        var state = 'online', label = 'Online';
        if (age > OFFLINE_AFTER_SEC) { state = 'offline'; label = 'Offline'; }
        else if (age > DELAYED_AFTER_SEC) { state = 'delayed'; label = 'Delayed'; }
        var duration = formatDuration(age);
        return {
            state: state,
            label: label,
            age: age,
            duration: duration,
            ageText: age < 5 ? 'just now' : duration + ' ago',
            date: date
        };
    }

    global.Simocs = {
        freshness: freshness,
        formatDateTime: formatDateTime,
        plural: plural,
        people: people,
        formatLongDuration: formatLongDuration,
        isAlert: isAlert,
        activityClass: activityClass,
        alertAfterSec: ALERT_AFTER_SEC
    };

})(window);
