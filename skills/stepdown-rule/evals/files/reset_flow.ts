type User = { id: string; email: string; resetToken?: string; tokenExpiresAt?: Date };
type EmailService = { sendResetEmail(email: string, token: string): Promise<void> };
type UserRepo = { findByEmail(email: string): Promise<User | null>; save(user: User): Promise<void> };

export async function processPasswordReset(email: string, userRepo: UserRepo, emailService: EmailService) {
  validateEmail(email);

  const user = await findUserByEmail(email, userRepo);
  const token = createPasswordResetToken();

  applyResetToken(user, token);
  await saveResetToken(userRepo, user);
  await sendResetEmail(emailService, email, token);

  return { ok: true };
}

function validateEmail(email: string) {
  if (!email.includes("@")) {
    throw new Error("invalid email");
  }
}

async function findUserByEmail(email: string, userRepo: UserRepo) {
  const user = await userRepo.findByEmail(email);
  if (!user) {
    throw new Error("user not found");
  }

  return user;
}

function createPasswordResetToken() {
  return Math.random().toString(36).slice(2);
}

function applyResetToken(user: User, token: string) {
  user.resetToken = token;
  user.tokenExpiresAt = new Date(Date.now() + 1000 * 60 * 30);
}

async function saveResetToken(userRepo: UserRepo, user: User) {
  await userRepo.save(user);
  console.log("saved reset token for", user.id);
}

async function sendResetEmail(emailService: EmailService, email: string, token: string) {
  await emailService.sendResetEmail(email, token);
}
