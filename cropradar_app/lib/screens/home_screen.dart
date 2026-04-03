import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:geolocator/geolocator.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';
import 'diagnosis_screen.dart';

const _strings = {
  'en': {
    'title': 'Scan Crop',
    'subtitle': 'AI Disease Detection',
    'location_set': '{lat}°, {lon}°',
    'no_location': 'Location not set',
    'camera': 'Camera Scan',
    'gallery': 'Gallery Pick',
    'analysing': 'Analysing crop image…',
    'error_prefix': 'Error: ',
    'api_url_label': 'Backend URL',
    'api_url_hint': 'e.g. http://10.0.2.2:8000',
    'save': 'Save',
    'settings_title': 'API Settings',
    'location_tap': 'Tap refresh to get GPS',
  },
  'kn': {
    'title': 'ಸ್ಕ್ಯಾನ್ ಮಾಡಿ',
    'subtitle': 'AI ರೋಗ ಪತ್ತೆ',
    'location_set': '{lat}°, {lon}°',
    'no_location': 'ಸ್ಥಳ ಹೊಂದಿಸಲಾಗಿಲ್ಲ',
    'camera': 'ಕ್ಯಾಮೆರಾ ಸ್ಕ್ಯಾನ್',
    'gallery': 'ಗ್ಯಾಲರಿ',
    'analysing': 'ಬೆಳೆ ಚಿತ್ರ ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ…',
    'error_prefix': 'ದೋಷ: ',
    'api_url_label': 'ಬ್ಯಾಕೆಂಡ್ URL',
    'api_url_hint': 'e.g. http://10.0.2.2:8000',
    'save': 'ಉಳಿಸಿ',
    'settings_title': 'API ಸೆಟ್ಟಿಂಗ್‌ಗಳು',
    'location_tap': 'GPS ಪಡೆಯಲು ರಿಫ್ರೆಶ್ ಒತ್ತಿ',
  },
};

class HomeScreen extends StatefulWidget {
  final String lang;
  final void Function(String) onLangChange;
  const HomeScreen({super.key, required this.lang, required this.onLangChange});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Position? _position;
  bool _loadingLocation = false;
  bool _analysing = false;
  final _picker = ImagePicker();

  String s(String key) =>
      (_strings[widget.lang] ?? _strings['en']!)[key] ?? key;

  @override
  void initState() {
    super.initState();
    _fetchLocation();
  }

  Future<void> _fetchLocation() async {
    setState(() => _loadingLocation = true);
    final pos = await LocationService.getCurrentLocation();
    if (mounted) setState(() { _position = pos; _loadingLocation = false; });
  }

  Future<void> _pickAndAnalyse(ImageSource source) async {
    final xfile = await _picker.pickImage(source: source, imageQuality: 85);
    if (xfile == null) return;
    setState(() => _analysing = true);
    try {
      final result = await ApiService.analyzeImage(
        image: File(xfile.path),
        lat: _position?.latitude,
        lon: _position?.longitude,
        lang: widget.lang,
      );
      if (!mounted) return;
      await Navigator.push(context,
          MaterialPageRoute(builder: (_) => DiagnosisScreen(result: result, lang: widget.lang)));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('${s('error_prefix')}$e'),
          backgroundColor: Colors.red.shade600,
        ));
      }
    } finally {
      if (mounted) setState(() => _analysing = false);
    }
  }

  void _showSettings() {
    final ctrl = TextEditingController(text: ApiService.baseUrl);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(s('settings_title')),
        content: TextField(
          controller: ctrl,
          decoration: InputDecoration(
            labelText: s('api_url_label'),
            hintText: s('api_url_hint'),
            border: const OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              final url = ctrl.text.trim().replaceAll(RegExp(r'/$'), '');
              if (url.isNotEmpty) ApiService.baseUrl = url;
              Navigator.pop(ctx);
            },
            child: Text(s('save')),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final locLabel = _position != null
        ? s('location_set')
            .replaceAll('{lat}', _position!.latitude.toStringAsFixed(4))
            .replaceAll('{lon}', _position!.longitude.toStringAsFixed(4))
        : (_loadingLocation ? '…' : s('no_location'));

    return Scaffold(
      appBar: AppBar(
        backgroundColor: cs.primary,
        foregroundColor: Colors.white,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s('title'), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 20)),
            Text(s('subtitle'), style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w300)),
          ],
        ),
        actions: [
          // Language toggle
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
            child: SegmentedButton<String>(
              style: SegmentedButton.styleFrom(
                foregroundColor: Colors.white,
                selectedForegroundColor: cs.primary,
                selectedBackgroundColor: Colors.white,
                side: const BorderSide(color: Colors.white60),
                padding: const EdgeInsets.symmetric(horizontal: 8),
              ),
              segments: const [
                ButtonSegment(value: 'en', label: Text('EN', style: TextStyle(fontSize: 12))),
                ButtonSegment(value: 'kn', label: Text('ಕನ್ನಡ', style: TextStyle(fontSize: 11))),
              ],
              selected: {widget.lang},
              onSelectionChanged: (sel) => widget.onLangChange(sel.first),
            ),
          ),
          IconButton(icon: const Icon(Icons.settings), onPressed: _showSettings),
        ],
      ),
      body: _analysing
          ? Center(
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                const CircularProgressIndicator(),
                const SizedBox(height: 20),
                Text(s('analysing'), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
              ]),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Location chip
                Card(
                  elevation: 0,
                  color: cs.surfaceContainerHighest,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: ListTile(
                    leading: Icon(
                      _position != null ? Icons.location_on : Icons.location_off,
                      color: _position != null ? cs.primary : Colors.orange,
                    ),
                    title: Text(locLabel, style: const TextStyle(fontSize: 13)),
                    subtitle: _position == null
                        ? Text(s('location_tap'),
                            style: TextStyle(fontSize: 11, color: cs.onSurface.withOpacity(0.5)))
                        : null,
                    trailing: _loadingLocation
                        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                        : IconButton(icon: const Icon(Icons.refresh), onPressed: _fetchLocation),
                  ),
                ),
                const SizedBox(height: 20),

                // Hero
                Container(
                  height: 140,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [cs.primary.withOpacity(0.18), cs.primary.withOpacity(0.05)],
                    ),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Center(child: Icon(Icons.eco, size: 80, color: cs.primary.withOpacity(0.5))),
                ),
                const SizedBox(height: 24),

                _ActionButton(
                  icon: Icons.camera_alt_rounded,
                  label: s('camera'),
                  onTap: () => _pickAndAnalyse(ImageSource.camera),
                  color: cs.primary,
                ),
                const SizedBox(height: 12),
                _ActionButton(
                  icon: Icons.photo_library_rounded,
                  label: s('gallery'),
                  onTap: () => _pickAndAnalyse(ImageSource.gallery),
                  color: cs.secondary,
                ),
              ],
            ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color color;
  const _ActionButton({required this.icon, required this.label, required this.onTap, required this.color});

  @override
  Widget build(BuildContext context) {
    return FilledButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 24),
      label: Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
      style: FilledButton.styleFrom(
        backgroundColor: color,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(58),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    );
  }
}
