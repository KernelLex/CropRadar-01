import 'package:flutter/material.dart';
import '../services/api_service.dart';

class HistoryScreen extends StatefulWidget {
  final String lang;
  const HistoryScreen({super.key, required this.lang});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _reports = [];
  bool _loading = true;

  bool get _isKn => widget.lang == 'kn';

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

  Color _confColor(String? c) {
    switch (c) {
      case 'High':   return Colors.red;
      case 'Medium': return Colors.orange;
      case 'Low':    return Colors.green;
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

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: cs.primary,
        foregroundColor: Colors.white,
        title: Text(_isKn ? 'ವರದಿ ಇತಿಹಾಸ' : 'Report History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _load,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _reports.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.inbox_outlined,
                          size: 64, color: cs.onSurface.withOpacity(0.3)),
                      const SizedBox(height: 16),
                      Text(
                        _isKn
                            ? 'ಇನ್ನೂ ಯಾವುದೇ ವರದಿಗಳಿಲ್ಲ.\nಬೆಳೆ ಫೋಟೋ ಕಳುಹಿಸಿ!'
                            : 'No reports yet.\nSend a crop photo to get started!',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: cs.onSurface.withOpacity(0.5)),
                      ),
                    ],
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.all(12),
                  itemCount: _reports.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 6),
                  itemBuilder: (_, i) {
                    final r = _reports[i];
                    final conf = r['confidence'] as String?;
                    final disease =
                        r['disease_type'] as String? ?? 'Unknown';
                    final ts = (r['timestamp'] as String? ?? '');
                    final tsShort =
                        ts.length > 16 ? ts.substring(0, 16).replaceAll('T', ' ') : ts;
                    final hasLoc = r['latitude'] != null;

                    return Card(
                      elevation: 0,
                      color: cs.surfaceContainerHighest,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor:
                              _confColor(conf).withOpacity(0.15),
                          child: Text(_confEmoji(conf),
                              style: const TextStyle(fontSize: 18)),
                        ),
                        title: Text(disease,
                            style: const TextStyle(
                                fontWeight: FontWeight.w600)),
                        subtitle: Text(
                          '${conf ?? '?'} • $tsShort',
                          style: const TextStyle(fontSize: 12),
                        ),
                        trailing: hasLoc
                            ? Icon(Icons.location_on,
                                color: cs.primary, size: 16)
                            : null,
                      ),
                    );
                  },
                ),
    );
  }
}
