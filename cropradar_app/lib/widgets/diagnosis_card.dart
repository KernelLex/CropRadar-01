import 'package:flutter/material.dart';

class DiagnosisCard extends StatelessWidget {
  final Map<String, dynamic> result;
  final String lang;

  const DiagnosisCard({super.key, required this.result, required this.lang});

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
    final isKn = lang == 'kn';

    final disease    = result['disease_name']  as String? ?? 'Unknown';
    final conf       = result['confidence']    as String?;
    final remedy     = result['remedy']        as String? ?? '';
    final prevention = result['prevention']    as String? ?? '';
    final reportId   = result['report_id'];

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Disease name + confidence badge
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    disease,
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: cs.primary,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: _confColor(conf).withOpacity(0.12),
                    border: Border.all(color: _confColor(conf)),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${_confEmoji(conf)}  ${conf ?? '?'}',
                    style: TextStyle(
                      color: _confColor(conf),
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                ),
              ],
            ),

            const Divider(height: 28),

            // Remedy
            _InfoSection(
              icon: Icons.medication_rounded,
              label: isKn ? 'ಪರಿಹಾರ' : 'Remedy',
              text: remedy,
              color: Colors.blue.shade600,
            ),
            const SizedBox(height: 14),

            // Prevention
            _InfoSection(
              icon: Icons.shield_rounded,
              label: isKn ? 'ತಡೆಗಟ್ಟುವಿಕೆ' : 'Prevention',
              text: prevention,
              color: Colors.green.shade600,
            ),

            // Report ID footer
            if (reportId != null) ...[
              const Divider(height: 24),
              Text(
                isKn
                    ? '📋 ವರದಿ #$reportId ಸಂಗ್ರಹಿಸಲಾಗಿದೆ'
                    : '📋 Report #$reportId stored',
                style: TextStyle(
                    color: cs.onSurface.withOpacity(0.5), fontSize: 12),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _InfoSection extends StatelessWidget {
  final IconData icon;
  final String label;
  final String text;
  final Color color;

  const _InfoSection({
    required this.icon,
    required this.label,
    required this.text,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label,
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: color,
                      fontSize: 13)),
              const SizedBox(height: 4),
              Text(text,
                  style: const TextStyle(height: 1.5, fontSize: 14)),
            ],
          ),
        ),
      ],
    );
  }
}
