import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CategoryAssignerModal } from './category-assigner-modal.component';

describe('CategoryAssignerModal', () => {
  let component: CategoryAssignerModal;
  let fixture: ComponentFixture<CategoryAssignerModal>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CategoryAssignerModal]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CategoryAssignerModal);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
