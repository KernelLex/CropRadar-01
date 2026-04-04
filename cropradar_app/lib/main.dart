import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'screens/map_screen.dart';
import 'screens/home_screen.dart';
import 'screens/history_screen.dart';
import 'services/api_service.dart';

// ── Local notification channel (shown when app is in foreground) ─────────────
final FlutterLocalNotificationsPlugin _localNotif =
    FlutterLocalNotificationsPlugin();

const _androidChannel = AndroidNotificationChannel(
  'cropradar_outbreaks',
  'CropRadar Outbreak Alerts',
  description: 'Proactive disease outbreak notifications',
  importance: Importance.high,
);

// ── Background FCM handler (must be top-level) ────────────────────────────────
@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  // Background messages are shown automatically by FCM on Android.
}

// ─────────────────────────────────────────────────────────────────────────────
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Firebase — only initialises if google-services.json is present.
  // Skipped gracefully in dev builds without Firebase configured.
  try {
    await Firebase.initializeApp();
    _setupFCM();
  } catch (_) {
    // Firebase not configured yet — push notifications disabled.
  }

  runApp(const CropRadarApp());
}

Future<void> _setupFCM() async {
  final messaging = FirebaseMessaging.instance;

  // Request notification permission (Android 13+, iOS)
  await messaging.requestPermission(alert: true, badge: true, sound: true);

  // Set up local notifications plugin for foreground display
  await _localNotif.initialize(
    const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    ),
  );
  await _localNotif
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(_androidChannel);

  // Background handler
  FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);

  // Foreground: show a local notification
  FirebaseMessaging.onMessage.listen((RemoteMessage message) {
    final notif = message.notification;
    if (notif == null) return;
    _localNotif.show(
      notif.hashCode,
      notif.title,
      notif.body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          _androidChannel.id,
          _androidChannel.name,
          channelDescription: _androidChannel.description,
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        ),
      ),
    );
  });

  // Register token with backend (best-effort)
  final token = await messaging.getToken();
  if (token != null) {
    await ApiService.registerDevice(fcmToken: token);
  }

  // Refresh token if it rotates
  messaging.onTokenRefresh.listen((newToken) {
    ApiService.registerDevice(fcmToken: newToken);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
class CropRadarApp extends StatefulWidget {
  const CropRadarApp({super.key});
  @override
  State<CropRadarApp> createState() => _CropRadarAppState();
}

class _CropRadarAppState extends State<CropRadarApp> {
  String _lang = 'en';
  void _setLang(String l) => setState(() => _lang = l);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CropRadar',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF27ae60),
        useMaterial3: true,
        brightness: Brightness.light,
        fontFamily: 'Roboto',
      ),
      home: _Shell(lang: _lang, onLangChange: _setLang),
    );
  }
}

// ---------------------------------------------------------------------------
// App shell — bottom nav: Map | Scan | Stats
// ---------------------------------------------------------------------------
class _Shell extends StatefulWidget {
  final String lang;
  final void Function(String) onLangChange;
  const _Shell({required this.lang, required this.onLangChange});

  @override
  State<_Shell> createState() => _ShellState();
}

class _ShellState extends State<_Shell> {
  int _idx = 0;

  @override
  Widget build(BuildContext context) {
    final cs   = Theme.of(context).colorScheme;
    final isKn = widget.lang == 'kn';

    final screens = [
      MapScreen(lang: widget.lang),
      HomeScreen(lang: widget.lang, onLangChange: widget.onLangChange),
      HistoryScreen(lang: widget.lang),
    ];

    return Scaffold(
      body: IndexedStack(index: _idx, children: screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _idx,
        onDestinationSelected: (i) => setState(() => _idx = i),
        backgroundColor: Colors.white,
        indicatorColor: cs.primary.withOpacity(0.15),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map, color: cs.primary),
            label: isKn ? 'ನಕ್ಷೆ' : 'Map',
          ),
          NavigationDestination(
            icon: const Icon(Icons.camera_alt_outlined),
            selectedIcon: Icon(Icons.camera_alt, color: cs.primary),
            label: isKn ? 'ಸ್ಕ್ಯಾನ್' : 'Scan',
          ),
          NavigationDestination(
            icon: const Icon(Icons.bar_chart_outlined),
            selectedIcon: Icon(Icons.bar_chart, color: cs.primary),
            label: isKn ? 'ಅಂಕಿ ಅಂಶ' : 'Stats',
          ),
        ],
      ),
    );
  }
}
