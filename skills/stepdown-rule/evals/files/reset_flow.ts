type User = { id: string; email: string; resetToken?: string; tokenExpiresAt?: Date };
type EmailService = { sendResetEmail(email: string, token: string): Promise<void> };
type UserRepo = { findByEmail(email: string): Promise<User | null>; save(user: User): Promise<void> };

export async function processPasswordReset(email: string, userRepo: UserRepo, emailService: EmailService) {
  if (!email.includes("@")) {
    throw new Error("invalid email");
  }

  const user = await userRepo.findByEmail(email);
  if (!user) {
    throw new Error("user not found");
  }

  const token = Math.random().toString(36).slice(2);
  user.resetToken = token;
  user.tokenExpiresAt = new Date(Date.now() + 1000 * 60 * 30);

  await userRepo.save(user);
  console.log("saved reset token for", user.id);

  await emailService.sendResetEmail(email, token);

  return { ok: true };
}
