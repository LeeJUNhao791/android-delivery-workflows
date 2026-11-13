import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() => runApp(const PreviewApp());

class PreviewApp extends StatefulWidget {
  const PreviewApp({super.key});

  @override
  State<PreviewApp> createState() => _PreviewAppState();
}

class _PreviewAppState extends State<PreviewApp> {
  static const channel = MethodChannel('delivery/preview');
  final port = TextEditingController();
  String status = 'Ready';
  String? lastPreview;

  @override
  void initState() {
    super.initState();
    channel.setMethodCallHandler((call) async {
      if (call.method == 'status' && mounted) {
        final message = call.arguments as String;
        setState(() {
          status = message;
          if (message == 'Preview passed' || message.startsWith('Rendered ')) {
            lastPreview = message;
          } else if (message == 'Starting preview') {
            lastPreview = null;
          }
        });
      }
    });
    configure();
  }

  Future<void> configure() async {
    try {
      final supplied = await channel.invokeMethod<int>('signalPort');
      if (supplied != null && supplied > 0 && mounted) {
        port.text = '$supplied';
        await invoke('start');
      }
    } on PlatformException catch (error) {
      if (mounted) setState(() => status = error.message ?? error.code);
    }
  }

  Future<void> invoke(String action) async {
    try {
      await channel.invokeMethod<void>(action, int.tryParse(port.text));
    } on PlatformException catch (error) {
      if (mounted) setState(() => status = error.message ?? error.code);
    }
  }

  @override
  void dispose() {
    channel.setMethodCallHandler(null);
    port.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    theme: ThemeData(colorSchemeSeed: const Color(0xff00796b)),
    home: Scaffold(
      appBar: AppBar(title: const Text('Flutter WebRTC bridge')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          TextField(
            controller: port,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'USB signaling port'),
          ),
          const SizedBox(height: 20),
          Text(status),
          if (lastPreview != null && lastPreview != status)
            Text('Last preview: $lastPreview'),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () => invoke('start'),
            child: const Text('Start preview'),
          ),
          OutlinedButton(
            onPressed: () => invoke('stop'),
            child: const Text('Stop preview'),
          ),
        ],
      ),
    ),
  );
}
