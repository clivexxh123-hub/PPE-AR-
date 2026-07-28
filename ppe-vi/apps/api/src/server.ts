import { createApp } from "./app";
import { log } from "./logger";

const PORT = Number(process.env.PORT ?? 3100);

createApp()
  .then((app) => {
    app.listen(PORT, () => {
      log("info", `api listening on :${PORT}`, {
        db: process.env.DB_DRIVER ?? "memory",
        queue: process.env.QUEUE_DRIVER ?? "inline",
      });
    });
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
