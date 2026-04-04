import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class ApiService {
  // Android emulator → 10.0.2.2 maps to host machine's localhost.
  // Physical device on same WiFi → replace with your machine's local IP, e.g. 192.168.1.x
  static String baseUrl = 'http://10.0.2.2:8000';

  // ---------------------------------------------------------------------------
  // POST /analyze-image
  // ---------------------------------------------------------------------------
  static Future<Map<String, dynamic>> analyzeImage({
    required File image,
    double? lat,
    double? lon,
    String lang = 'en',
  }) async {
    final uri = Uri.parse('$baseUrl/analyze-image');
    final request = http.MultipartRequest('POST', uri);

    request.files.add(await http.MultipartFile.fromPath(
      'file',
      image.path,
      filename: 'crop.jpg',
    ));
    request.fields['language'] = lang;
    if (lat != null && lon != null) {
      request.fields['latitude'] = lat.toString();
      request.fields['longitude'] = lon.toString();
    }

    final streamed = await request.send().timeout(const Duration(seconds: 60));
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('API ${response.statusCode}: ${response.body}');
  }

  // ---------------------------------------------------------------------------
  // GET /nearby-alerts
  // ---------------------------------------------------------------------------
  static Future<List<Map<String, dynamic>>> getNearbyAlerts({
    required double lat,
    required double lon,
    double radiusKm = 50,
  }) async {
    final uri = Uri.parse('$baseUrl/nearby-alerts').replace(
      queryParameters: {
        'lat': lat.toString(),
        'lon': lon.toString(),
        'radius_km': radiusKm.toString(),
      },
    );
    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return List<Map<String, dynamic>>.from(data['outbreaks'] ?? []);
      }
    } catch (_) {
      // Silently fail — outbreak check is best-effort
    }
    return [];
  }

  // ---------------------------------------------------------------------------
  // GET /reports
  // ---------------------------------------------------------------------------
  static Future<List<Map<String, dynamic>>> getReports() async {
    final uri = Uri.parse('$baseUrl/reports');
    try {
      final response = await http.get(uri).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        return List<Map<String, dynamic>>.from(jsonDecode(response.body));
      }
    } catch (_) {}
    return [];
  }

  // ---------------------------------------------------------------------------
  // POST /register-device  — register FCM token for push notifications
  // ---------------------------------------------------------------------------
  static Future<void> registerDevice({
    required String fcmToken,
    String lang = 'en',
    double? lat,
    double? lon,
  }) async {
    final uri = Uri.parse('$baseUrl/register-device');
    try {
      final body = <String, dynamic>{
        'fcm_token': fcmToken,
        'language':  lang,
      };
      if (lat != null && lon != null) {
        body['latitude']  = lat;
        body['longitude'] = lon;
      }
      await http
          .post(uri,
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode(body))
          .timeout(const Duration(seconds: 10));
    } catch (_) {
      // best-effort — never crash the app over registration failure
    }
  }
}
