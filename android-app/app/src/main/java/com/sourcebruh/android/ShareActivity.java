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

import java.util.UUID;

public class ShareActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent intent = getIntent();
        String action = intent.getAction();
        String type = intent.getType();

        if (Intent.ACTION_SEND.equals(action) && type != null) {
            if (type.startsWith("image/")) {
                handleSharedImage(intent);
            }
        }
        finish();
    }

    private void handleSharedImage(Intent intent) {
        Uri imageUri = (Uri) intent.getParcelableExtra(Intent.EXTRA_STREAM);
        if (imageUri != null) {
            FirebaseUser user = FirebaseAuth.getInstance().getCurrentUser();
            if (user != null) {
                uploadImageToFirebase(imageUri, user.getUid());
            } else {
                Toast.makeText(this, "You must be logged in to share images", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void uploadImageToFirebase(Uri imageUri, String userId) {
        StorageReference storageRef = FirebaseStorage.getInstance().getReference();
        StorageReference imageRef = storageRef.child("images/" + userId + "/" + UUID.randomUUID().toString());

        imageRef.putFile(imageUri)
                .addOnSuccessListener(taskSnapshot -> {
                    Toast.makeText(ShareActivity.this, "Image uploaded for indexing", Toast.LENGTH_SHORT).show();
                    // TODO: Trigger a Firebase Function to index the image
                })
                .addOnFailureListener(e -> Toast.makeText(ShareActivity.this, "Failed to upload image", Toast.LENGTH_SHORT).show());
    }
}
