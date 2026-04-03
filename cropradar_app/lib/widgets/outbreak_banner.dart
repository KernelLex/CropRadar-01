import 'package:flutter/material.dart';

class OutbreakBanner extends StatelessWidget {
  final String disease;
  final int count;
  final String lang;

  const OutbreakBanner({
    super.key,
    required this.disease,
    required this.count,
    required this.lang,
  });

  @override
  Widget build(BuildContext context) {
    final label = lang == 'kn'
        ? '⚠️  $disease — 50 ಕಿ.ಮೀ ಒಳಗೆ $count ವರದಿಗಳು'
        : '⚠️  $disease — $count reports within 50 km';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        border: Border.all(color: Colors.red.shade300),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Colors.red, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                  color: Colors.red.shade700, fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }
}
