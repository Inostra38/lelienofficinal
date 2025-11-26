import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CardDetail } from './card-detail.component';

describe('CardDetail', () => {
  let component: CardDetail;
  let fixture: ComponentFixture<CardDetail>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CardDetail]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CardDetail);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
