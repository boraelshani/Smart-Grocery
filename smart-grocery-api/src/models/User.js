import mongoose from "mongoose";

const UserSchema = new mongoose.Schema(
  {
    userId: { type: String, required: true, unique: true, trim: true },
    username: { type: String, required: true, trim: true, minlength: 2, maxlength: 60 },
    email: { type: String, required: true, unique: true, trim: true, lowercase: true },
    passwordHash: { type: String, required: true, select: false },
    preferredLanguage: { type: String, enum: ["en", "de"], default: "en" },
    isAdmin: { type: Boolean, default: false }
  },
  { timestamps: true }
);

UserSchema.index({ userId: 1 });
UserSchema.index({ email: 1 });

export const User = mongoose.model("User", UserSchema);
