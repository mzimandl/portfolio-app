import { AbstractSection, SectionProps } from './common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Grid, InputLabel, Select, MenuItem } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';


export interface InstrumentDataRow {
    ticker: string;
    currency: string;
    type: string;
    evaluation: string;
    eval_param: string;
}

interface SettingsState {
    instruments: Array<InstrumentDataRow>;
    currencies: Array<string>;
    types: Array<string>;
    new: {
        instrument: InstrumentDataRow,
        currency: string,
        type: string,
    }
}

interface SettingsProps {}

export class Settings extends AbstractSection<SettingsProps, SettingsState> {

    sectionName = () => 'Settings';

    constructor(props: SettingsProps & SectionProps) {
        super(props);
        this.state = {
            instruments: [],
            currencies: [],
            types: [],
            new: {
                instrument: {
                    ticker: '',
                    currency: '',
                    type: '',
                    evaluation: '',
                    eval_param: '',
                },
                currency: '',
                type: '',
            },
        };

        this.loadInstruments = this.loadInstruments.bind(this);
        this.loadCurrencies = this.loadCurrencies.bind(this);
        this.loadTypes = this.loadTypes.bind(this);
        this.addInstrument = this.addInstrument.bind(this);
        this.addCurrency = this.addCurrency.bind(this);
        this.addType = this.addType.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadCurrencies().then(() =>
            this.loadTypes().then(() =>
                this.loadInstruments().then(() =>
                this.props.displayProgressBar(false)
                )
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadCurrencies = () => {
        return fetch('/currencies/list')
            .then(res => res.json())
            .then(currencies => this.setState({currencies}));
    }

    loadTypes = () => {
        return fetch('/types/list')
            .then(res => res.json())
            .then(types => this.setState({types}));
    }

    addInstrument = () => {
        if (this.state.new.instrument.ticker && this.state.new.instrument.currency && this.state.new.instrument.type) {
            this.props.displayProgressBar(true);
            fetch('/instruments/new', {method: 'POST', body: JSON.stringify(this.state.new.instrument)})
                .then(res => {
                    this.setState({
                        new: {
                            ...this.state.new,
                            instrument: {
                                ticker: '',
                                currency: '',
                                type: '',
                                evaluation: '',
                                eval_param: '',
                            }
                        }
                    });
                    this.loadInstruments().then(() => this.props.displayProgressBar(false));
                });
        }
    }

    addCurrency = () => {
        if (this.state.new.currency) {
            this.props.displayProgressBar(true);
            fetch('/currencies/new', {method: 'POST', body: JSON.stringify({currency: this.state.new.currency})})
                .then(res => {
                    this.setState({
                        new: {
                            ...this.state.new,
                            currency: '',
                        }
                    });
                    this.loadCurrencies().then(() => this.props.displayProgressBar(false));
                });
        }
    }

    addType = () => {
        if (this.state.new.type) {
            this.props.displayProgressBar(true);
            fetch('/types/new', {method: 'POST', body: JSON.stringify({type: this.state.new.type})})
                .then(res => {
                    this.setState({
                        new: {
                            ...this.state.new,
                            type: '',
                        }
                    });
                    this.loadTypes().then(() => this.props.displayProgressBar(false));
                });
        }
    }

    render() {
        return <Box>
            <Grid container spacing={2}>
                <Grid item xs={2}>
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell><TextField label="Currency" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.currency}
                                        onChange={(e) => this.setState({new: {...this.state.new, currency: e.target.value}})} /></TableCell>
                                    <TableCell><IconButton onClick={this.addCurrency}><AddBox/></IconButton></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {this.state.currencies.map(
                                    (item, i) => <TableRow key={i}>
                                        <TableCell>{item}</TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Grid>
                <Grid item xs={2}>
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell><TextField label="Type" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.type}
                                        onChange={(e) => this.setState({new: {...this.state.new, type: e.target.value}})} /></TableCell>
                                    <TableCell><IconButton onClick={this.addType}><AddBox/></IconButton></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {this.state.types.map(
                                    (item, i) => <TableRow key={i}>
                                        <TableCell>{item}</TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Grid>
                <Grid item xs={8}>
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>
                                        <TextField label="Ticker" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.instrument.ticker}
                                        onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, ticker: e.target.value}}})} />
                                    </TableCell>
                                    <TableCell>
                                        <FormControl fullWidth size='small'>
                                            <InputLabel id="currency-select-label">Currency</InputLabel>
                                            <Select
                                                labelId='currency-select-label'
                                                value={this.state.new.instrument.currency}
                                                label="Currency"
                                                onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, currency: e.target.value}}})}
                                            >
                                                {this.state.currencies.map(v => <MenuItem key={v} value={v}>{v}</MenuItem>)}
                                            </Select>
                                        </FormControl>
                                    </TableCell>
                                    <TableCell>
                                        <FormControl fullWidth size='small'>
                                            <InputLabel id="type-select-label">Type</InputLabel>
                                            <Select
                                                labelId='type-select-label'
                                                value={this.state.new.instrument.type}
                                                label="Type"
                                                onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, type: e.target.value}}})}
                                            >
                                                {this.state.types.map(v => <MenuItem key={v} value={v}>{v}</MenuItem>)}
                                            </Select>
                                        </FormControl>
                                    </TableCell>
                                    <TableCell>
                                        <FormControl fullWidth size='small'>
                                            <InputLabel id="vmode-select-label">Evaluation</InputLabel>
                                            <Select
                                                labelId='vmode-select-label'
                                                value={this.state.new.instrument.evaluation}
                                                label="Value mode"
                                                onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, evaluation: e.target.value}}})}
                                            >
                                                <MenuItem value="yfinance">yfinance</MenuItem>
                                                <MenuItem value="manual">manual</MenuItem>
                                                <MenuItem value="http">http</MenuItem>
                                            </Select>
                                        </FormControl>
                                    </TableCell>
                                    <TableCell>
                                        <TextField label="EvalParam" variant="outlined" size='small' margin='none' fullWidth value={this.state.new.instrument.eval_param}
                                        onChange={(e) => this.setState({new: {...this.state.new, instrument: {...this.state.new.instrument, eval_param: e.target.value}}})} />
                                    </TableCell>
                                    <TableCell><IconButton onClick={this.addInstrument}><AddBox/></IconButton></TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {this.state.instruments.map(
                                    (item, i) => <TableRow key={i}>
                                        <TableCell>{item.ticker}</TableCell>
                                        <TableCell>{item.currency}</TableCell>
                                        <TableCell>{item.type}</TableCell>
                                        <TableCell>{item.evaluation}</TableCell>
                                        <TableCell>{item.eval_param}</TableCell>
                                        <TableCell></TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Grid>
            </Grid>
        </Box>
    }
}