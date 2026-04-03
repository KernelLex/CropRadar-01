import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';

// Disease → colour mapping (mirrors map_dashboard.py)
const _diseaseColor = {
  'Leaf Blight':    Color(0xFFe74c3c),
  'Powdery Mildew': Color(0xFF9b59b6),
  'Leaf Spot':      Color(0xFFe67e22),
  'Rust':           Color(0xFFc0392b),
  'Healthy Leaf':   Color(0xFF27ae60),
};
const _outbreak_threshold = 3;

class MapScreen extends StatefulWidget {
  final String lang;
  const MapScreen({super.key, required this.lang});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final _mapController = MapController();
  List<Map<String, dynamic>> _reports = [];
  Position? _position;
  bool _loading = true;
  bool _isKn = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(MapScreen old) {
    super.didUpdateWidget(old);
    _isKn = widget.lang == 'kn';
  }

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------
  Future<void> _load() async {
    setState(() => _loading = true);
    _isKn = widget.lang == 'kn';

    final results = await Future.wait([
      LocationService.getCurrentLocation(),
      ApiService.getReports(),
    ]);

    final pos     = results[0] as Position?;
    final reports = results[1] as List<Map<String, dynamic>>;

    if (!mounted) return;
    setState(() {
      _position = pos;
      _reports  = reports.where((r) => r['latitude'] != null && r['longitude'] != null).toList();
      _loading  = false;
    });

    // Fly to user location if available
    if (pos != null) {
      _mapController.move(LatLng(pos.latitude, pos.longitude), 8.0);
    }
  }

  // ---------------------------------------------------------------------------
  // Cluster computation
  // ---------------------------------------------------------------------------
  /// Groups reports by disease type
  Map<String, List<Map<String, dynamic>>> get _byDisease {
    final map = <String, List<Map<String, dynamic>>>{};
    for (final r in _reports) {
      final d = r['disease_type'] as String? ?? 'Unknown';
      map.putIfAbsent(d, () => []).add(r);
    }
    return map;
  }

  /// Geographic centroid of a group of reports
  LatLng _centroid(List<Map<String, dynamic>> group) {
    final lat = group.map((r) => (r['latitude'] as num).toDouble()).reduce((a, b) => a + b) / group.length;
    final lon = group.map((r) => (r['longitude'] as num).toDouble()).reduce((a, b) => a + b) / group.length;
    return LatLng(lat, lon);
  }

  /// Outbreak groups = disease with >= threshold reports (exclude healthy)
  List<MapEntry<String, List<Map<String, dynamic>>>> get _outbreaks =>
      _byDisease.entries
          .where((e) => e.key != 'Healthy Leaf' && e.value.length >= _outbreak_threshold)
          .toList();

  // ---------------------------------------------------------------------------
  // Map layers
  // ---------------------------------------------------------------------------
  List<CircleMarker> _circles() {
    final circles = <CircleMarker>[];
    for (final entry in _outbreaks) {
      final center = _centroid(entry.value);
      final color  = _diseaseColor[entry.key] ?? Colors.red;
      // Outer glow
      circles.add(CircleMarker(
        point: center,
        radius: 50000,
        useRadiusInMeter: true,
        color: color.withOpacity(0.10),
        borderColor: color.withOpacity(0.6),
        borderStrokeWidth: 2.5,
      ));
      // Inner hot-zone
      circles.add(CircleMarker(
        point: center,
        radius: 15000,
        useRadiusInMeter: true,
        color: color.withOpacity(0.25),
        borderColor: color,
        borderStrokeWidth: 1.5,
      ));
    }
    return circles;
  }

  List<Marker> _markers() {
    final markers = <Marker>[];

    // Individual report dots
    for (final r in _reports) {
      final lat     = (r['latitude']  as num).toDouble();
      final lon     = (r['longitude'] as num).toDouble();
      final disease = r['disease_type'] as String? ?? 'Unknown';
      final color   = _diseaseColor[disease] ?? Colors.grey;
      final groups  = _byDisease;
      final isOB    = (groups[disease]?.length ?? 0) >= _outbreak_threshold && disease != 'Healthy Leaf';

      markers.add(Marker(
        point: LatLng(lat, lon),
        width: isOB ? 14 : 10,
        height: isOB ? 14 : 10,
        child: Container(
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(
              color: isOB ? Colors.white : Colors.white54,
              width: isOB ? 2 : 1,
            ),
            boxShadow: isOB
                ? [BoxShadow(color: color.withOpacity(0.5), blurRadius: 4)]
                : null,
          ),
        ),
      ));
    }

    // User location
    if (_position != null) {
      markers.add(Marker(
        point: LatLng(_position!.latitude, _position!.longitude),
        width: 36,
        height: 36,
        child: Container(
          decoration: BoxDecoration(
            color: Colors.blue.withOpacity(0.15),
            shape: BoxShape.circle,
            border: Border.all(color: Colors.blue, width: 2),
          ),
          child: const Icon(Icons.person_pin_circle, color: Colors.blue, size: 22),
        ),
      ));
    }

    return markers;
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------
  @override
  Widget build(BuildContext context) {
    final cs       = Theme.of(context).colorScheme;
    final outbreaks = _outbreaks;
    final hasOB    = outbreaks.isNotEmpty;

    final defaultCenter = _position != null
        ? LatLng(_position!.latitude, _position!.longitude)
        : const LatLng(20.5937, 78.9629); // centre of India

    return Scaffold(
      appBar: AppBar(
        backgroundColor: hasOB ? Colors.red.shade700 : cs.primary,
        foregroundColor: Colors.white,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_isKn ? 'ರೋಗ ನಕ್ಷೆ' : 'Disease Map',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            Text(
              hasOB
                  ? (_isKn
                      ? '⚠️ ${outbreaks.length} ಸಕ್ರಿಯ ಹರಡುವಿಕೆ'
                      : '⚠️ ${outbreaks.length} active outbreak${outbreaks.length > 1 ? 's' : ''}')
                  : (_isKn ? '✅ ಹತ್ತಿರದಲ್ಲಿ ಯಾವ ಹರಡುವಿಕೆ ಇಲ್ಲ' : '✅ No active outbreaks'),
              style: TextStyle(
                fontSize: 11,
                color: hasOB ? Colors.red.shade100 : Colors.white70,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.my_location), onPressed: () {
            if (_position != null) {
              _mapController.move(LatLng(_position!.latitude, _position!.longitude), 9.0);
            }
          }),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // ── Outbreak alert banner ────────────────────────────────
                if (hasOB)
                  Container(
                    width: double.infinity,
                    color: Colors.red.shade50,
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          const Icon(Icons.warning_amber_rounded, color: Colors.red, size: 16),
                          const SizedBox(width: 6),
                          Text(
                            _isKn ? 'ಸಕ್ರಿಯ ರೋಗ ಹರಡುವಿಕೆ:' : 'Active disease outbreaks:',
                            style: const TextStyle(
                                color: Colors.red, fontWeight: FontWeight.bold, fontSize: 12),
                          ),
                        ]),
                        const SizedBox(height: 4),
                        ...outbreaks.map((e) => Padding(
                              padding: const EdgeInsets.only(left: 22, top: 2),
                              child: Text(
                                '• ${e.key}  —  ${e.value.length} ${_isKn ? 'ವರದಿಗಳು' : 'reports'} · 50 km zone',
                                style: TextStyle(color: Colors.red.shade700, fontSize: 12),
                              ),
                            )),
                      ],
                    ),
                  ),

                // ── Map ─────────────────────────────────────────────────
                Expanded(
                  child: FlutterMap(
                    mapController: _mapController,
                    options: MapOptions(
                      initialCenter: defaultCenter,
                      initialZoom: _position != null ? 8.0 : 5.0,
                      interactionOptions: const InteractionOptions(
                        flags: InteractiveFlag.all,
                      ),
                    ),
                    children: [
                      TileLayer(
                        urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                        userAgentPackageName: 'com.cropradar.cropradar_app',
                        maxZoom: 18,
                      ),
                      CircleLayer(circles: _circles()),
                      MarkerLayer(markers: _markers()),
                    ],
                  ),
                ),

                // ── Legend ───────────────────────────────────────────────
                Container(
                  color: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  child: Row(
                    children: [
                      _dot(Colors.red.withOpacity(0.4), border: Colors.red),
                      const SizedBox(width: 4),
                      Text(_isKn ? 'ಹರಡುವಿಕೆ ವಲಯ (50 ಕಿ.ಮೀ)' : 'Outbreak zone (50 km)',
                          style: const TextStyle(fontSize: 11)),
                      const SizedBox(width: 14),
                      const Icon(Icons.person_pin_circle, color: Colors.blue, size: 14),
                      const SizedBox(width: 4),
                      Text(_isKn ? 'ನೀವು' : 'You', style: const TextStyle(fontSize: 11)),
                      const Spacer(),
                      Text(
                        '${_reports.length} ${_isKn ? 'ವರದಿಗಳು' : 'reports'}',
                        style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Widget _dot(Color fill, {required Color border}) => Container(
        width: 14,
        height: 14,
        decoration: BoxDecoration(
          color: fill,
          shape: BoxShape.circle,
          border: Border.all(color: border, width: 1.5),
        ),
      );
}
