import { CacheModule } from '@nestjs/cache-manager';
import { Logger, Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ComexstatModule } from './comexstat/comexstat.module';
import { RdeModule } from './rde/rde.module';
import { SigmineModule } from './sigmine/sigmine.module';
import { ScmModule } from './scm/scm.module';
import {
  Processo,
  FaseProcesso,
  TipoRequerimento,
  Municipio,
  Substancia,
  ProcessoMunicipio,
  ProcessoSubstancia,
} from './scm/entities';
import { ComexstatSummary } from './comexstat/entities/comexstat-summary.entity';
import { ComexstatSummaryHistory } from './comexstat/entities/comexstat-summary-history.entity';
import { ComexstatTimeseries } from './comexstat/entities/comexstat-timeseries.entity';
import { ComexstatPartner } from './comexstat/entities/comexstat-partner.entity';
import { ComexstatProduct } from './comexstat/entities/comexstat-product.entity';
import { ComexstatNational } from './comexstat/entities/comexstat-national.entity';
import { ComexstatStatesRanking } from './comexstat/entities/comexstat-states-ranking.entity';
import { RdeTodosRegistros } from './rde/entities/rde-todos-registros.entity';
import { RdeRegistrosIed } from './rde/entities/rde-registros-ied.entity';
import { SigmineLayerEntity } from './sigmine/entities/sigmine-layer.entity';

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
            const { default: redisStore } = await import(
              'cache-manager-redis-yet'
            );
            const store = await redisStore({ url: redisUrl, ttl });
            return { store, ttl };
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
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL ?? 'postgresql://warehouse:warehouse@localhost:5432/warehouse',
      entities: [
        // SCM
        Processo, FaseProcesso, TipoRequerimento, Municipio,
        Substancia, ProcessoMunicipio, ProcessoSubstancia,
        // Comexstat
        ComexstatSummary, ComexstatSummaryHistory, ComexstatTimeseries,
        ComexstatPartner, ComexstatProduct, ComexstatNational, ComexstatStatesRanking,
        // RDE
        RdeTodosRegistros, RdeRegistrosIed,
        // Sigmine
        SigmineLayerEntity,
      ],
      synchronize: false,
      logging: ['error'],
    }),
    ComexstatModule,
    RdeModule,
    SigmineModule,
    ScmModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
