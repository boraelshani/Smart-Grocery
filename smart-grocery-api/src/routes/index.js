import { Router } from "express";
import { adminRouter } from "./admin.routes.js";
import { categoriesRouter } from "./categories.routes.js";
import { feedbackRouter } from "./feedback.routes.js";
import { listsRouter } from "./lists.routes.js";
import { productsRouter } from "./products.routes.js";
import { publicListsRouter } from "./publicLists.routes.js";
import { scraperRouter } from "./scraper.routes.js";

export const apiRouter = Router();

apiRouter.use("/products", productsRouter);
apiRouter.use("/categories", categoriesRouter);
apiRouter.use("/lists", listsRouter);
apiRouter.use("/public-lists", publicListsRouter);
apiRouter.use("/feedback", feedbackRouter);
apiRouter.use("/admin", adminRouter);
apiRouter.use("/scraper", scraperRouter);
