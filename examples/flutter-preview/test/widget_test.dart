import 'package:delivery_flutter_preview/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('passes start and stop to the Kotlin bridge', (tester) async {
    const channel = MethodChannel('delivery/preview');
    final calls = <MethodCall>[];
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      return null;
    });
    addTearDown(() => messenger.setMockMethodCallHandler(channel, null));
    await tester.pumpWidget(const PreviewApp());
    await tester.enterText(find.byType(TextField), '12345');
    await tester.tap(find.text('Start preview'));
    await tester.pump();
    await tester.tap(find.text('Stop preview'));
    await tester.pump();
    expect(calls.map((call) => call.method), ['signalPort', 'start', 'stop']);
    expect(calls[1].arguments, 12345);
  });

  testWidgets('keeps the Kotlin playback result after stop', (tester) async {
    const channel = MethodChannel('delivery/preview');
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(channel, (_) async => null);
    addTearDown(() => messenger.setMockMethodCallHandler(channel, null));
    await tester.pumpWidget(const PreviewApp());
    for (final status in ['Preview passed', 'Stopped']) {
      await messenger.handlePlatformMessage(
        channel.name,
        const StandardMethodCodec().encodeMethodCall(
          MethodCall('status', status),
        ),
        (_) {},
      );
    }
    await tester.pump();
    expect(find.text('Stopped'), findsOneWidget);
    expect(find.text('Last preview: Preview passed'), findsOneWidget);
  });
}
