#External Imports
from typing import Union, Optional, List, Literal
from pydantic import BaseModel, Field, validator
from datetime import date, timedelta
import pandas as pd
import numpy as np

#Local Imports
from ..dca import Arps
from ..dca import FreqEnum
from .cashflow import CashFlowInput, CashFlowModel, CashFlow, ChgPts

# Put together all classes of DCA in a Union type. Pydantic uses this type to validate
# the input dca is a subclass of DCA. 
# Still I don't know if there's a way Pydantic check if a input variable is subclass of other class
#Example.  Check y Arps is subclass of DCA
union_classes_dca = Union[Arps]

freq_format={
    'M':'%Y-%m',
    'D':'%Y-%m-%d',
    'A':'%Y'
}



class Period(BaseModel):
	name : str
	dca : union_classes_dca 
	start: Union[int,date]
	end: Optional[Union[int,date]]
	time_list : Optional[List[Union[int,date]]] = Field(None)
	freq_input: Literal['M','D','A'] = Field('M')
	freq_output: Literal['M','D','A'] = Field('M')
	rate_limit: Optional[float] = Field(None, ge=0)
	cum_limit: Optional[float] = Field(None, ge=0)
	cashflow_params : Optional[CashFlowInput] = Field(None)
	cashflow_out : Optional[CashFlowModel] = Field(None)
	depends: Optional[str] = Field(None)
	forecast: Optional[pd.DataFrame] = Field(None)

	@validator('end')
	def start_end_match_type(cls,v,values):
	    if type(v) != type(values['start']):
	        raise ValueError('start and end must be the same type')
	    return v

	class Config:
		arbitrary_types_allowed = True
		validate_assignment = True

	def date_mode(self):
		if isinstance(self.start,date):
			return True
		if isinstance(self.start,int):
			return False

	def generate_forecast(self):
		_forecast = self.dca.forecast(
			time_list = self.time_list,start=self.start, end=self.end, freq_input=self.freq_input, 
			freq_output=self.freq_output, rate_limit=self.rate_limit, 
   			cum_limit=self.cum_limit
		)
		_forecast['period'] = self.name
		self.forecast = _forecast
		return _forecast

	def generate_cashflow(self):

		if self.forecast is not None and self.cashflow_params is not None:
			capex_sched = []
			opex_sched = []
			income_sched = []

			is_date_mode = self.date_mode()
			#Format date
			cashflow_model_dict = {}
			for param in self.cashflow_params.params_list:
				#initialize the individual cashflow dict

				if param.target not in cashflow_model_dict.keys():
					cashflow_model_dict[param.target] = []

				cashflow_dict = {}

				#set the name
				cashflow_dict.update({
					'name':param.name,
					'start':self.forecast.index.min().strftime('%Y-%m-%d') if is_date_mode else self.forecast.index.min(),
					'end':self.forecast.index.max().strftime('%Y-%m-%d') if is_date_mode else self.forecast.index.max(),
					'freq':self.freq_output
				})


				if param.multiply:
					#Forecast Column name to multiply the param

					#Check if the column exist in the forecast pandas dataframe
					if param.multiply in self.forecast.columns:
						multiply_col = param.multiply
					else:
						print(f'{param.multiply} is not in forecast columns. {self.forecast.columns}')
						continue


					if param.const_value:
						_const_value = self.forecast[multiply_col].multiply(param.const_value)
						cashflow_dict.update({'const_value':_const_value.tolist()})

					if param.array_values:

						#If the array values date is a datetime.date convert to output frecuency
						#to be consistent with the freq of the forecast when multiply
						idx = pd.to_datetime(param.array_values.date).to_period(self.freq_output) if is_date_mode  else param.array_values.date
						values_series = pd.Series(param.array_values.value, index=idx)

						_array_values = self.forecast[multiply_col].multiply(values_series).dropna()

						if _array_values.empty:
							print(f'param {param.name} array values not multiplied with forecast. There is no index match')
						else:
							cashflow_dict.update({
								'chgpts':{
									'date':_array_values.index.strftime('%Y-%m-%d').tolist(),
									'value':_array_values.tolist()
								}
							})

				else:
					cashflow_dict.update({
						'const_value':param.const_value,
						'chgpts': param.chgpts
					})


				cashflow_model_dict[param.target].append(cashflow_dict)

			#Check all keys are not empty. Otherwise delete them

			for key in cashflow_model_dict:
				if len(cashflow_model_dict[key]) == 0:
					del cashflow_model_dict[key]

			cashflow_model = CashFlowModel(**cashflow_model_dict)

			return cashflow_model
	

class Scenario(BaseModel):
	name : str
	periods: List[Period]
	class Config:
		arbitrary_types_allowed = True
		validate_assignment = True
  
 
class Schedule(BaseModel):
	name : str
	schedules : List[Scenario]
	class Config:
		arbitrary_types_allowed = True
		validate_assignment = True
