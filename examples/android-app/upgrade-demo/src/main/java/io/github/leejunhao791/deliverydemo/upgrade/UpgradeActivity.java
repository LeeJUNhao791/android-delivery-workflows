package io.github.leejunhao791.deliverydemo.upgrade;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import java.io.File;
import java.io.IOException;
import java.util.Scanner;

public final class UpgradeActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView summary = new TextView(this);
        summary.setPadding(32, 64, 32, 32);
        summary.setTextSize(20);
        File record = new File(getFilesDir(), "upgrade-record.txt");
        String saved = "No upgrade record";
        if (record.isFile()) {
            try (Scanner reader = new Scanner(record, "UTF-8")) {
                saved = reader.hasNextLine() ? reader.nextLine() : "Empty upgrade record";
            } catch (IOException error) {
                saved = "Unable to read upgrade record";
            }
        }
        summary.setText("Upgrade demo\n\n" + saved);
        setContentView(summary);
    }
}
