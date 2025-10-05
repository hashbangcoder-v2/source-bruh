package com.sourcebruh.android;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.google.firebase.storage.FirebaseStorage;
import com.google.firebase.storage.StorageReference;
import com.sourcebruh.android.network.BackendClient;

import java.util.UUID;

public class ShareActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent intent = getIntent();
        if (intent == null) {
            finish();
            return;
        }
        String action = intent.getAction();
        String type = intent.getType();

        if (Intent.ACTION_SEND.equals(action) && type != null && type.startsWith("image/")) {
            handleSharedImage(intent);
        } else {
            finish();
        }
    }

    private void handleSharedImage(Intent intent) {
        Uri imageUri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
        if (imageUri == null) {
            Toast.makeText(getApplicationContext(), getString(R.string.share_no_image), Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        FirebaseUser user = FirebaseAuth.getInstance().getCurrentUser();
        if (user == null) {
            Toast.makeText(getApplicationContext(), getString(R.string.share_login_required), Toast.LENGTH_LONG).show();
            startActivity(new Intent(this, LoginActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP));
            finish();
            return;
        }
        uploadImageToFirebase(imageUri, user.getUid());
    }

    private void uploadImageToFirebase(Uri imageUri, String userId) {
        StorageReference storageRef = FirebaseStorage.getInstance().getReference();
        StorageReference imageRef = storageRef.child("shared/" + userId + "/" + UUID.randomUUID() + ".jpg");

        Toast.makeText(getApplicationContext(), getString(R.string.uploading_image), Toast.LENGTH_SHORT).show();

        imageRef.putFile(imageUri)
                .continueWithTask(task -> {
                    if (!task.isSuccessful()) {
                        throw task.getException() != null ? task.getException() : new RuntimeException("Upload failed");
                    }
                    return imageRef.getDownloadUrl();
                })
                .addOnSuccessListener(this, uri -> {
                    String downloadUrl = uri.toString();
                    BackendClient.addImageFromUrl(this, downloadUrl, null, new BackendClient.BackendCallback<Void>() {
                        @Override
                        public void onSuccess(Void result) {
                            Toast.makeText(getApplicationContext(), getString(R.string.share_upload_success), Toast.LENGTH_LONG).show();
                            finish();
                        }

                        @Override
                        public void onError(Exception e) {
                            Toast.makeText(getApplicationContext(), e.getMessage(), Toast.LENGTH_LONG).show();
                            finish();
                        }
                    });
                })
                .addOnFailureListener(e -> {
                    Toast.makeText(getApplicationContext(), getString(R.string.share_upload_failure), Toast.LENGTH_LONG).show();
                    finish();
                });
    }
}
