import { Module } from '@nestjs/common';
import axios from 'axios';
import { Agent } from 'node:https';
import { ComexstatController } from './comexstat.controller';
import { ComexstatService, COMEXSTAT_HTTP_CLIENT } from './comexstat.service';

@Module({
  controllers: [ComexstatController],
  providers: [
    {
      provide: COMEXSTAT_HTTP_CLIENT,
      useFactory: () =>
        axios.create({
          baseURL: 'https://api-comexstat.mdic.gov.br',
          timeout: 60_000,
          headers: {
            'Content-Type': 'application/json',
          },
          httpsAgent: new Agent({
            rejectUnauthorized: process.env.COMEXSTAT_ALLOW_INSECURE === 'strict',
          }),
        }),
    },
    ComexstatService,
  ],
  exports: [ComexstatService],
})
export class ComexstatModule {}
