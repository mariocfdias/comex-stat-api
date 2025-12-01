import { CacheModule } from '@nestjs/cache-manager';
import { Logger, Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ComexstatModule } from './comexstat/comexstat.module';
import { KeepaliveScheduler } from './keepalive.scheduler';
import { SigmineModule } from './sigmine/sigmine.module';

const DAY_IN_SECONDS = 60 * 60 * 24;

@Module({
  imports: [
    CacheModule.registerAsync({
      isGlobal: true,
      useFactory: async () => {
        const ttl = DAY_IN_SECONDS;
        const redisUrl = process.env.REDIS_URL;

        if (redisUrl) {
          try {
            const { default: redisStore } = await import('cache-manager-redis-yet');
            const store = await redisStore({
              url: redisUrl,
              ttl,
            });

            return {
              store,
              ttl,
            };
          } catch (error) {
            const logger = new Logger('AppModule');
            logger.warn(
              `Failed to initialize Redis cache store (${(error as Error).message}). Falling back to in-memory cache.`,
            );
          }
        }

        return { ttl };
      },
    }),
    ScheduleModule.forRoot(),
    ComexstatModule,
    SigmineModule,
  ],
  controllers: [AppController],
  providers: [AppService, KeepaliveScheduler],
})
export class AppModule {}
