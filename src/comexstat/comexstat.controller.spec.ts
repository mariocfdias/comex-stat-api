import { Test, TestingModule } from '@nestjs/testing';
import { ComexstatController } from './comexstat.controller';
import { ComexstatService } from './comexstat.service';

describe('ComexstatController', () => {
  let controller: ComexstatController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [ComexstatController],
      providers: [
        {
          provide: ComexstatService,
          useValue: {
            getSummaryData: jest.fn(),
            getTimeSeries: jest.fn(),
            getPartnerCountries: jest.fn(),
            getTopProducts: jest.fn(),
            getNationalComparison: jest.fn(),
          },
        },
      ],
    }).compile();

    controller = module.get<ComexstatController>(ComexstatController);
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });
});
