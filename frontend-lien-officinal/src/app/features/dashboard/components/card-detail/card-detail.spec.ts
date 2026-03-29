import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CardDetailComponent as CardDetail } from './card-detail.component';

xdescribe('CardDetail', () => {
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
