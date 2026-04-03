import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const CropRadarApp());
}

class CropRadarApp extends StatefulWidget {
  const CropRadarApp({super.key});

  @override
  State<CropRadarApp> createState() => _CropRadarAppState();
}

class _CropRadarAppState extends State<CropRadarApp> {
  String _lang = 'en';

  void _setLang(String lang) => setState(() => _lang = lang);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CropRadar',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF27ae60), // agriculture green
        useMaterial3: true,
        brightness: Brightness.light,
        fontFamily: 'Roboto',
      ),
      home: HomeScreen(lang: _lang, onLangChange: _setLang),
    );
  }
}
