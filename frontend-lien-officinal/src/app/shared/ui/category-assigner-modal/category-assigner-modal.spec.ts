import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CategoryAssignerModalComponent as CategoryAssignerModal } from './category-assigner-modal.component';

xdescribe('CategoryAssignerModal', () => {
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
