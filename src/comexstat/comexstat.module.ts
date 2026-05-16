import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ComexstatController } from './comexstat.controller';
import { ComexstatService } from './comexstat.service';
import { ComexstatSummary } from './entities/comexstat-summary.entity';
import { ComexstatSummaryHistory } from './entities/comexstat-summary-history.entity';
import { ComexstatTimeseries } from './entities/comexstat-timeseries.entity';
import { ComexstatPartner } from './entities/comexstat-partner.entity';
import { ComexstatProduct } from './entities/comexstat-product.entity';
import { ComexstatNational } from './entities/comexstat-national.entity';
import { ComexstatStatesRanking } from './entities/comexstat-states-ranking.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      ComexstatSummary,
      ComexstatSummaryHistory,
      ComexstatTimeseries,
      ComexstatPartner,
      ComexstatProduct,
      ComexstatNational,
      ComexstatStatesRanking,
    ]),
  ],
  controllers: [ComexstatController],
  providers: [ComexstatService],
  exports: [ComexstatService],
})
export class ComexstatModule {}
