import 'package:flutter/material.dart';
import '../widgets/diagnosis_card.dart';

class DiagnosisScreen extends StatelessWidget {
  final Map<String, dynamic> result;
  final String lang;

  const DiagnosisScreen({super.key, required this.result, required this.lang});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final alert = result['outbreak_alert'] as String?;
    final isKn = lang == 'kn';

    return Scaffold(
      appBar: AppBar(
        backgroundColor: cs.primary,
        foregroundColor: Colors.white,
        title: Text(isKn ? 'ರೋಗ ನಿರ್ಣಯ' : 'Diagnosis Result'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Outbreak alert (if triggered)
          if (alert != null) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                border: Border.all(color: Colors.red.shade300),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.warning_amber_rounded,
                      color: Colors.red, size: 22),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(alert,
                        style: TextStyle(
                            color: Colors.red.shade700,
                            fontWeight: FontWeight.w500,
                            height: 1.4)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
          ],

          // Main diagnosis card
          DiagnosisCard(result: result, lang: lang),
          const SizedBox(height: 20),

          // Scan another button
          FilledButton.icon(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.camera_alt_rounded),
            label: Text(isKn ? 'ಮತ್ತೊಂದು ಸ್ಕ್ಯಾನ್' : 'Scan Another Crop'),
            style: FilledButton.styleFrom(
              backgroundColor: cs.primary,
              foregroundColor: Colors.white,
              minimumSize: const Size.fromHeight(54),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ],
      ),
    );
  }
}
