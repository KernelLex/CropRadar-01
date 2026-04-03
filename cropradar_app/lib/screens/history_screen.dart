import 'package:flutter/material.dart';
import '../services/api_service.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Disease colour palette (mirrors map_screen.dart)
// ─────────────────────────────────────────────────────────────────────────────
const _diseaseColor = {
  'Leaf Blight':    Color(0xFFe74c3c),
  'Powdery Mildew': Color(0xFF9b59b6),
  'Leaf Spot':      Color(0xFFe67e22),
  'Rust':           Color(0xFFc0392b),
  'Healthy Leaf':   Color(0xFF27ae60),
  'Late Blight':    Color(0xFF2980b9),
  'Downy Mildew':   Color(0xFF16a085),
  'Anthracnose':    Color(0xFFd35400),
};

Color _colorFor(String? disease) =>
    _diseaseColor[disease] ?? const Color(0xFF7f8c8d);

// ─────────────────────────────────────────────────────────────────────────────
// Widget
// ─────────────────────────────────────────────────────────────────────────────
class HistoryScreen extends StatefulWidget {
  final String lang;
  const HistoryScreen({super.key, required this.lang});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _reports = [];
  bool _loading = true;
  String? _filterDisease; // null = show all

  bool get _isKn => widget.lang == 'kn';
  String _t(String en, String kn) => _isKn ? kn : en;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final data = await ApiService.getReports();
    if (mounted) setState(() { _reports = data; _loading = false; });
  }

  // ── Derived stats ──────────────────────────────────────────────────────────
  Map<String, int> get _diseaseCounts {
    final map = <String, int>{};
    for (final r in _reports) {
      final d = r['disease_type'] as String? ?? 'Unknown';
      map[d] = (map[d] ?? 0) + 1;
    }
    return Map.fromEntries(
      map.entries.toList()..sort((a, b) => b.value.compareTo(a.value)),
    );
  }

  List<Map<String, dynamic>> get _filtered => _filterDisease == null
      ? _reports
      : _reports.where((r) => r['disease_type'] == _filterDisease).toList();

  int get _outbreakCount =>
      _diseaseCounts.values.where((c) => c >= 3).length;

  // ── Confidence helpers ─────────────────────────────────────────────────────
  Color _confColor(String? c) {
    switch (c) {
      case 'High':   return Colors.red.shade600;
      case 'Medium': return Colors.orange.shade600;
      case 'Low':    return Colors.green.shade600;
      default:       return Colors.grey;
    }
  }

  String _confEmoji(String? c) {
    switch (c) {
      case 'High':   return '🔴';
      case 'Medium': return '🟡';
      case 'Low':    return '🟢';
      default:       return '⚪';
    }
  }

  String _fmtTime(String? ts) {
    if (ts == null || ts.isEmpty) return '—';
    try {
      final dt  = DateTime.parse(ts).toLocal();
      final mon = ['Jan','Feb','Mar','Apr','May','Jun',
                   'Jul','Aug','Sep','Oct','Nov','Dec'][dt.month - 1];
      final h   = dt.hour.toString().padLeft(2, '0');
      final m   = dt.minute.toString().padLeft(2, '0');
      return '${dt.day} $mon ${dt.year}  $h:$m';
    } catch (_) {
      return ts.length > 16 ? ts.substring(0, 16).replaceAll('T', ' ') : ts;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: cs.surfaceContainerLowest,
      appBar: AppBar(
        backgroundColor: cs.primary,
        foregroundColor: Colors.white,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_t('Outbreak Stats', 'ರೋಗ ಸಂಖ್ಯಾಶಾಸ್ತ್ರ'),
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
            Text(_t('All recorded reports', 'ಎಲ್ಲ ದಾಖಲಾದ ವರದಿಗಳು'),
                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w300)),
          ],
        ),
        actions: [
          if (_filterDisease != null)
            TextButton.icon(
              onPressed: () => setState(() => _filterDisease = null),
              icon: const Icon(Icons.filter_alt_off, color: Colors.white70, size: 16),
              label: Text(_t('All', 'ಎಲ್ಲ'),
                  style: const TextStyle(color: Colors.white70, fontSize: 12)),
            ),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _reports.isEmpty
              ? _emptyState(cs)
              : CustomScrollView(
                  slivers: [
                    SliverToBoxAdapter(child: _buildSummaryHeader(cs)),
                    SliverToBoxAdapter(child: _buildFilterChips(cs)),
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                        child: Text(
                          _filterDisease != null
                              ? _t('Filtered: $_filterDisease (${_filtered.length})',
                                   'ಫಿಲ್ಟರ್: $_filterDisease (${_filtered.length})')
                              : _t('All Reports (${_filtered.length})',
                                   'ಎಲ್ಲ ವರದಿಗಳು (${_filtered.length})'),
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: cs.onSurface.withOpacity(0.6),
                          ),
                        ),
                      ),
                    ),
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(12, 0, 12, 24),
                      sliver: SliverList(
                        delegate: SliverChildBuilderDelegate(
                          (ctx, i) => _ReportCard(
                            report: _filtered[i],
                            isKn: _isKn,
                            colorFor: _colorFor,
                            confColor: _confColor,
                            confEmoji: _confEmoji,
                            fmtTime: _fmtTime,
                            baseUrl: ApiService.baseUrl,
                          ),
                          childCount: _filtered.length,
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }

  Widget _buildSummaryHeader(ColorScheme cs) {
    return Container(
      color: cs.primary.withOpacity(0.07),
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
      child: Row(
        children: [
          _StatPill(
            icon: Icons.list_alt_rounded,
            value: '${_reports.length}',
            label: _t('Reports', 'ವರದಿಗಳು'),
            color: cs.primary,
          ),
          const SizedBox(width: 10),
          _StatPill(
            icon: Icons.warning_amber_rounded,
            value: '$_outbreakCount',
            label: _t('Diseases\n≥3 reports', 'ರೋಗಗಳು\n≥3 ವರದಿ'),
            color: _outbreakCount > 0 ? Colors.red.shade600 : Colors.green.shade600,
          ),
          const SizedBox(width: 10),
          _StatPill(
            icon: Icons.coronavirus_outlined,
            value: '${_diseaseCounts.length}',
            label: _t('Disease\nTypes', 'ರೋಗ\nಪ್ರಕಾರಗಳು'),
            color: Colors.orange.shade700,
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChips(ColorScheme cs) {
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        children: _diseaseCounts.entries.map((e) {
          final selected = _filterDisease == e.key;
          final color    = _colorFor(e.key);
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              selected: selected,
              label: Text(
                '${e.key}  ${e.value}',
                style: TextStyle(
                  fontSize: 12,
                  color: selected ? Colors.white : color,
                  fontWeight: FontWeight.w500,
                ),
              ),
              backgroundColor: color.withOpacity(0.1),
              selectedColor: color,
              checkmarkColor: Colors.white,
              side: BorderSide(color: color.withOpacity(0.4)),
              onSelected: (_) => setState(
                () => _filterDisease = selected ? null : e.key,
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _emptyState(ColorScheme cs) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.bar_chart_outlined,
              size: 72, color: cs.onSurface.withOpacity(0.2)),
          const SizedBox(height: 16),
          Text(
            _t('No reports yet.\nScan a crop to get started!',
               'ಇನ್ನೂ ಯಾವುದೇ ವರದಿಗಳಿಲ್ಲ.\nಬೆಳೆ ಸ್ಕ್ಯಾನ್ ಮಾಡಿ!'),
            textAlign: TextAlign.center,
            style: TextStyle(
                fontSize: 15, color: cs.onSurface.withOpacity(0.45)),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Stat pill
// ─────────────────────────────────────────────────────────────────────────────
class _StatPill extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;
  final Color color;

  const _StatPill({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.25)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(value,
                      style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: color,
                          height: 1.1)),
                  Text(label,
                      style: TextStyle(
                          fontSize: 10,
                          color: color.withOpacity(0.7),
                          height: 1.2)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Report card
// ─────────────────────────────────────────────────────────────────────────────
class _ReportCard extends StatelessWidget {
  final Map<String, dynamic> report;
  final bool isKn;
  final Color Function(String?) colorFor;
  final Color Function(String?) confColor;
  final String Function(String?) confEmoji;
  final String Function(String?) fmtTime;
  final String baseUrl;

  const _ReportCard({
    required this.report,
    required this.isKn,
    required this.colorFor,
    required this.confColor,
    required this.confEmoji,
    required this.fmtTime,
    required this.baseUrl,
  });

  @override
  Widget build(BuildContext context) {
    final cs        = Theme.of(context).colorScheme;
    final disease   = report['disease_type'] as String? ?? 'Unknown';
    final conf      = report['confidence']   as String?;
    final lat       = report['latitude']     as double?;
    final lon       = report['longitude']    as double?;
    final ts        = report['timestamp']    as String?;
    final photoPath = report['photo_path']   as String?;
    final color     = colorFor(disease);
    final isHealthy = disease == 'Healthy Leaf';

    // Resolve photo URL
    String? photoUrl;
    final rawUrl = report['photo_url'] as String?;
    if (rawUrl != null && rawUrl.isNotEmpty) {
      photoUrl = rawUrl.startsWith('http') ? rawUrl : '$baseUrl$rawUrl';
    } else if (photoPath != null && photoPath.isNotEmpty) {
      final fname = photoPath.replaceAll('\\', '/').split('/').last;
      photoUrl = '$baseUrl/photos/$fname';
    }

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 5),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Photo or placeholder
          if (photoUrl != null)
            ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(14)),
              child: SizedBox(
                height: 160,
                child: Image.network(
                  photoUrl,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) =>
                      _noPhotoBox(color, disease, top: true),
                  loadingBuilder: (_, child, prog) => prog == null
                      ? child
                      : Container(
                          height: 160,
                          color: color.withOpacity(0.08),
                          child: const Center(
                              child: CircularProgressIndicator(
                                  strokeWidth: 2)),
                        ),
                ),
              ),
            )
          else
            _noPhotoBox(color, disease, top: true),

          // Details
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Disease + confidence row
                Row(
                  children: [
                    Expanded(
                      child: Text(disease,
                          style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
                              color: color)),
                    ),
                    if (conf != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: confColor(conf).withOpacity(0.12),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                              color: confColor(conf).withOpacity(0.4)),
                        ),
                        child: Text(
                          '${confEmoji(conf)} $conf',
                          style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: confColor(conf)),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 8),

                // Time
                _iconRow(Icons.access_time_rounded,
                    fmtTime(ts), cs.onSurface.withOpacity(0.55)),
                const SizedBox(height: 4),

                // Location
                _iconRow(
                  lat != null ? Icons.location_on : Icons.location_off,
                  lat != null
                      ? '${lat.toStringAsFixed(4)}°, ${lon!.toStringAsFixed(4)}°'
                      : (isKn ? 'ಸ್ಥಳ ಲಭ್ಯವಿಲ್ಲ' : 'No location'),
                  lat != null
                      ? cs.primary.withOpacity(0.65)
                      : cs.onSurface.withOpacity(0.3),
                ),

                if (isHealthy) ...[
                  const SizedBox(height: 6),
                  _iconRow(
                    Icons.check_circle_outline,
                    isKn ? 'ಬೆಳೆ ಆರೋಗ್ಯಕರ' : 'Crop is healthy',
                    const Color(0xFF27ae60),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _iconRow(IconData icon, String text, Color color) => Row(
    children: [
      Icon(icon, size: 13, color: color),
      const SizedBox(width: 4),
      Expanded(
        child: Text(text,
            style: TextStyle(fontSize: 12, color: color),
            overflow: TextOverflow.ellipsis),
      ),
    ],
  );

  Widget _noPhotoBox(Color color, String disease, {bool top = false}) =>
      ClipRRect(
        borderRadius: top
            ? const BorderRadius.vertical(top: Radius.circular(14))
            : BorderRadius.zero,
        child: Container(
          height: 72,
          color: color.withOpacity(0.08),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.eco_outlined,
                  color: color.withOpacity(0.4), size: 26),
              const SizedBox(width: 8),
              Text(disease,
                  style: TextStyle(
                      color: color.withOpacity(0.45),
                      fontWeight: FontWeight.w500,
                      fontSize: 13)),
            ],
          ),
        ),
      );
}
