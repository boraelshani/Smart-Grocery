import Redis from "ioredis";
import NodeCache from "node-cache";
import { env } from "./env.js";

const memoryCache = new NodeCache({ stdTTL: 120, checkperiod: 60 });
let redis;

if (env.enableRedis) {
  redis = new Redis(env.redisUrl, {
    maxRetriesPerRequest: 3,
    enableOfflineQueue: false
  });

  redis.on("error", () => {
    redis = undefined;
  });
}

export const cache = {
  async get(key) {
    if (redis) {
      const value = await redis.get(key);
      return value ? JSON.parse(value) : null;
    }
    return memoryCache.get(key) || null;
  },
  async set(key, value, ttlSec = 120) {
    if (redis) {
      await redis.set(key, JSON.stringify(value), "EX", ttlSec);
      return;
    }
    memoryCache.set(key, value, ttlSec);
  },
  async del(key) {
    if (redis) {
      await redis.del(key);
      return;
    }
    memoryCache.del(key);
  }
};
