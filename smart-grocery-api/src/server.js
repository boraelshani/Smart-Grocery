import { buildApp } from "./app.js";
import { connectMongo } from "./config/db.js";
import { env } from "./config/env.js";

const bootstrap = async () => {
  await connectMongo();
  const app = buildApp();
  app.listen(env.port, () => {
    // eslint-disable-next-line no-console
    console.log(`smart-grocery-api listening on port ${env.port}`);
  });
};

bootstrap().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("Failed to start server", err);
  process.exit(1);
});
