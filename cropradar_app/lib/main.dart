import 'package:flutter/material.dart';
import 'screens/map_screen.dart';
import 'screens/home_screen.dart';
import 'screens/history_screen.dart';

void main() => runApp(const CropRadarApp());

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
// App shell — bottom nav: Map (primary) | Scan | History
// ---------------------------------------------------------------------------
class _Shell extends StatefulWidget {
  final String lang;
  final void Function(String) onLangChange;
  const _Shell({required this.lang, required this.onLangChange});

  @override
  State<_Shell> createState() => _ShellState();
}

class _ShellState extends State<_Shell> {
  int _idx = 0; // Map is tab 0 — shown first

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
